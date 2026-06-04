from __future__ import annotations

from abc import ABC, abstractmethod
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .errors import ParseError
from .fetch import Fetcher
from .models import Bill, DocumentLink, Jurisdiction, Progress


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _id_from_url(url: str, fallback: str) -> str:
    tail = url.rstrip("/").split("/")[-1]
    tail = tail.split("?")[-1].split("=")[-1]
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", tail or fallback).strip("-")


def _progress(status: str | None, unicameral: bool = False) -> Progress:
    lowered = (status or "").lower()
    assented = "assent" in lowered or "passed both" in lowered
    passed_lower = assented or any(
        token in lowered for token in ("passed lower", "passed assembly", "house")
    )
    passed_upper = assented or any(
        token in lowered for token in ("passed upper", "passed council", "senate")
    )
    if unicameral and ("introduced" in lowered or "current" in lowered or status):
        passed_lower = True
    if "third" in lowered:
        stage = "third reading"
    elif "second" in lowered:
        stage = "second reading"
    elif "first" in lowered or "introduced" in lowered:
        stage = "first reading"
    elif assented:
        stage = "assented"
    else:
        stage = status
    return Progress(
        current_stage=stage,
        passed_lower=passed_lower,
        passed_upper=passed_upper,
        assented=assented,
    )


class Adapter(ABC):
    jurisdiction: Jurisdiction
    list_url: str

    def __init__(self, fetcher: Fetcher):
        self.fetcher = fetcher

    @abstractmethod
    def list_bills(self) -> list[Bill]:
        raise NotImplementedError

    def get_bill(self, bill_id: str) -> Bill:
        for bill in self.list_bills():
            if bill.id == bill_id:
                return self._hydrate(bill)
        raise KeyError(f"No {self.jurisdiction.value} bill found for id {bill_id}")

    def _hydrate(self, bill: Bill) -> Bill:
        return bill

    def _html(self, url: str) -> BeautifulSoup:
        return _soup(self.fetcher.get_text(url))

    def _documents(self, soup: BeautifulSoup, base_url: str) -> list[DocumentLink]:
        docs = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = _clean(link.get_text(" "))
            if not href.lower().endswith((".pdf", ".doc", ".docx", ".html", ".htm")):
                if not any(word in text.lower() for word in ("bill", "memorandum", "statement")):
                    continue
            url = urljoin(base_url, href)
            kind = "explanatory memorandum" if "memorandum" in text.lower() else "bill"
            mime = "application/pdf" if ".pdf" in href.lower() else None
            docs.append(DocumentLink(url=url, kind=kind, mime_type=mime))
        return docs


class ACTAdapter(Adapter):
    jurisdiction = Jurisdiction.ACT
    list_url = "https://legislation.act.gov.au/results?category=cBil&status=Current&action=browse"

    def list_bills(self) -> list[Bill]:
        soup = self._html(self.list_url)
        table = soup.find("table", id="results-table-bill") or soup.find("table")
        if not table:
            raise ParseError("ACT bill table not found")
        bills = []
        for index, row in enumerate(table.find_all("tr")):
            cols = row.find_all("td")
            if len(cols) < 2 or not cols[1].find("a"):
                continue
            link = urljoin("https://legislation.act.gov.au", cols[1].find("a")["href"])
            status = _clean(cols[-1].get_text(" "))
            bills.append(Bill(
                id=_id_from_url(link, str(index)),
                jurisdiction=self.jurisdiction,
                title=_clean(cols[1].get_text(" ")),
                source_url=link,
                status=status,
                house="Assembly",
                introduced_date=cols[0].get("data-order") or _clean(cols[0].get_text(" ")),
                progress=_progress(status or "introduced", unicameral=True),
            ))
        return bills

    def _hydrate(self, bill: Bill) -> Bill:
        soup = self._html(bill.source_url)
        dds = soup.find_all("dd")
        bill.sponsor = _clean(dds[1].get_text(" ")) if len(dds) > 1 else bill.sponsor
        bill.documents = self._documents(soup, bill.source_url)
        return bill


class QLDAdapter(Adapter):
    jurisdiction = Jurisdiction.QLD
    list_url = "https://www.legislation.qld.gov.au/browse/bills"

    def list_bills(self) -> list[Bill]:
        soup = self._html(self.list_url)
        parl = _clean(soup.find("td").get_text(" "))[:2] if soup.find("td") else ""
        api = (
            "https://www.legislation.qld.gov.au/projectdata?ds=OQPC-BrowseDataSource"
            "&start=1&count=9999&sortField=year&sortDirection=asc&filterField=year"
            "&expression=Repealed%3DN+AND+PrintType%3D(%22bill.first%22+OR+"
            f"%22bill.firstnongovintro%22)+AND+ParliamentNo%3D{parl}"
            "&subset=browse&collection=&_=0"
        )
        data = self.fetcher.get_json(api)
        bills = []
        for item in data.get("data", []):
            title = item.get("title", {}).get("__value__", item.get("title", ""))
            bill_id = item.get("id", {}).get("__value__", item.get("id", title))
            date = item.get("publication.date")
            bills.append(Bill(
                id=str(bill_id),
                jurisdiction=self.jurisdiction,
                title=_clean(title),
                source_url=f"https://www.legislation.qld.gov.au/view/html/bill.first/{bill_id}",
                house="Assembly",
                introduced_date=date,
                progress=_progress("introduced", unicameral=True),
            ))
        if not bills:
            raise ParseError("QLD projectdata returned no bills")
        return bills

    def _hydrate(self, bill: Bill) -> Bill:
        soup = self._html(bill.source_url + "/lh")
        bill.status = _clean(soup.find("tr").get_text(" ")) if soup.find("tr") else bill.status
        bill.progress = _progress(bill.status or "introduced", unicameral=True)
        bill.documents = self._documents(soup, bill.source_url)
        return bill


class NTAdapter(Adapter):
    jurisdiction = Jurisdiction.NT
    list_url = "https://legislation.nt.gov.au/en/LegislationPortal/Bills/By-Session"

    def list_bills(self) -> list[Bill]:
        soup = self._html(self.list_url)
        table = soup.find("table")
        if not table:
            raise ParseError("NT bill table not found")
        bills = []
        for row in table.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) < 4 or not cols[2].find("a"):
                continue
            link = urljoin("https://legislation.nt.gov.au/en/LegislationPortal/Bills/", cols[2].find("a")["href"])
            passed = _clean(cols[4].get_text(" ")) if len(cols) > 4 else ""
            bills.append(Bill(
                id=_clean(cols[1].get_text(" ")) or _id_from_url(link, _clean(cols[2].get_text(" "))),
                jurisdiction=self.jurisdiction,
                title=_clean(cols[2].get_text(" ")),
                source_url=link,
                status="assented" if passed else "introduced",
                house="Assembly",
                introduced_date=_clean(cols[3].get_text(" ")),
                assent_date=passed or None,
                progress=_progress("assented" if passed else "introduced", unicameral=True),
            ))
        return bills

    def _hydrate(self, bill: Bill) -> Bill:
        soup = self._html(bill.source_url)
        fieldset = soup.find("fieldset")
        if fieldset:
            rows = fieldset.find_all(class_="row")
            if len(rows) > 2:
                bill.sponsor = _clean(rows[2].get_text(" "))
        bill.documents = self._documents(soup, bill.source_url)
        return bill


class WAAdapter(Adapter):
    jurisdiction = Jurisdiction.WA
    list_url = "https://www.parliament.wa.gov.au/parliament/bills.nsf/screenWebCurrentBills?OpenForm&Start=1&Count=-1"

    def list_bills(self) -> list[Bill]:
        soup = self._html(self.list_url)
        table = soup.find("table")
        if not table:
            raise ParseError("WA bill table not found")
        bills = []
        for index, row in enumerate(table.find_all("tr")):
            cols = row.find_all("td")
            if len(cols) < 3 or not cols[1].find("a"):
                continue
            link = urljoin("https://www.parliament.wa.gov.au", cols[1].find("a")["href"])
            status = _clean(cols[-1].get_text(" "))
            bills.append(Bill(
                id=_id_from_url(link, str(index)),
                jurisdiction=self.jurisdiction,
                title=_clean(cols[1].get_text(" ")),
                source_url=link,
                status=status,
                introduced_date=_clean(cols[2].get_text(" ")),
                assent_date=_clean(cols[-1].get_text(" ")).split("-")[-1].strip() if "assent" in status.lower() else None,
                progress=_progress(status),
            ))
        return bills

    def _hydrate(self, bill: Bill) -> Bill:
        soup = self._html(bill.source_url)
        rows = soup.find_all("tr")
        if len(rows) > 2:
            bill.summary = _clean(rows[2].get_text(" "))
        bill.documents = self._documents(soup, bill.source_url)
        return bill


class TASAdapter(Adapter):
    jurisdiction = Jurisdiction.TAS
    list_url = "https://www.parliament.tas.gov.au/bills"

    def list_bills(self) -> list[Bill]:
        soup = self._html(self.list_url)
        return self._list_from_links(soup, "https://www.parliament.tas.gov.au")

    def _list_from_links(self, soup: BeautifulSoup, base: str) -> list[Bill]:
        bills = []
        for index, link_tag in enumerate(soup.find_all("a", href=True)):
            title = _clean(link_tag.get_text(" "))
            href = link_tag["href"]
            if not title or "bill" not in (title + href).lower():
                continue
            url = urljoin(base, href)
            bills.append(Bill(
                id=_id_from_url(url, str(index)),
                jurisdiction=self.jurisdiction,
                title=title,
                source_url=url,
                status="current",
                progress=_progress("current"),
            ))
        if not bills:
            raise ParseError("TAS bill links not found")
        return bills

    def _hydrate(self, bill: Bill) -> Bill:
        soup = self._html(bill.source_url)
        text = soup.get_text(" ")
        match = re.search(r"Introduced by:\s*([^.\n]+)", text)
        bill.sponsor = _clean(match.group(1)) if match else bill.sponsor
        bill.documents = self._documents(soup, bill.source_url)
        return bill


class VICAdapter(TASAdapter):
    jurisdiction = Jurisdiction.VIC
    list_url = "https://www.legislation.vic.gov.au/bills/in-parliament"

    def list_bills(self) -> list[Bill]:
        soup = self._html(self.list_url)
        bills = self._list_from_links(soup, "https://www.legislation.vic.gov.au")
        for bill in bills:
            bill.status = "in parliament"
            bill.progress = _progress(bill.status)
        return bills


class SAAdapter(TASAdapter):
    jurisdiction = Jurisdiction.SA
    list_url = "https://legislation.sa.gov.au/legislation/bills"

    def list_bills(self) -> list[Bill]:
        soup = self._html(self.list_url)
        bills = self._list_from_links(soup, "https://legislation.sa.gov.au")
        for bill in bills:
            bill.status = "introduced"
            bill.progress = _progress("introduced")
        return bills


class NSWAdapter(Adapter):
    jurisdiction = Jurisdiction.NSW
    list_url = "https://legislation.nsw.gov.au/browse/bills"

    def list_bills(self) -> list[Bill]:
        soup = self._html(self.list_url)
        api = soup.find("a", href=re.compile("projectdata"))
        if api:
            data = self.fetcher.get_json(urljoin(self.list_url, api["href"]))
            return self._from_projectdata(data)
        bills = []
        for index, link in enumerate(soup.find_all("a", href=True)):
            title = _clean(link.get_text(" "))
            if "bill" not in title.lower():
                continue
            url = urljoin("https://legislation.nsw.gov.au", link["href"])
            bills.append(Bill(
                id=_id_from_url(url, str(index)),
                jurisdiction=self.jurisdiction,
                title=title,
                source_url=url,
                status="introduced",
                progress=_progress("introduced"),
            ))
        if not bills:
            raise ParseError("NSW bill links not found")
        return bills

    def _from_projectdata(self, data: object) -> list[Bill]:
        bills = []
        for item in data.get("data", []):
            title = item.get("title", {}).get("__value__", item.get("title", ""))
            record_id = item.get("record-id") or item.get("id") or title
            bills.append(Bill(
                id=str(record_id),
                jurisdiction=self.jurisdiction,
                title=_clean(title),
                source_url=f"https://legislation.nsw.gov.au/view/html/bill/{record_id}",
                status="introduced",
                progress=_progress("introduced"),
            ))
        if not bills:
            raise ParseError("NSW projectdata returned no bills")
        return bills

    def _hydrate(self, bill: Bill) -> Bill:
        soup = self._html(bill.source_url)
        type_span = soup.find(class_="bill-type")
        if type_span and "introduced by" in type_span.get_text(" ").lower():
            bill.sponsor = _clean(type_span.get_text(" ").split("introduced by", 1)[-1])
        bill.documents = self._documents(soup, bill.source_url)
        return bill


class FederalAdapter(Adapter):
    jurisdiction = Jurisdiction.FEDERAL
    list_url = "https://www.aph.gov.au/Parliamentary_Business/Bills_Legislation/Bills_before_Parliament?sr=0"

    def list_bills(self) -> list[Bill]:
        soup = self._html(self.list_url)
        bills = []
        for index, item in enumerate(soup.find_all("li")):
            heading = item.find("h4")
            link = heading.find("a", href=True) if heading else None
            if not link:
                continue
            title = _clean(link.get_text(" "))
            if not title:
                continue
            fields = {}
            for term in item.find_all("dt"):
                dd = term.find_next_sibling("dd")
                fields[_clean(term.get_text(" ")).lower()] = _clean(dd.get_text(" ")) if dd else None
            status = fields.get("status")
            url = urljoin("https://www.aph.gov.au", link["href"])
            documents = self._documents(item, url)
            bills.append(Bill(
                id=_id_from_url(url, str(index)),
                jurisdiction=self.jurisdiction,
                title=title,
                source_url=url,
                status=status,
                house=fields.get("chamber"),
                introduced_date=fields.get("date"),
                portfolio=fields.get("portfolio"),
                summary=fields.get("summary"),
                progress=_progress(status),
                documents=documents,
            ))
        if bills:
            return bills

        for index, row in enumerate(soup.find_all("tr")):
            link = row.find("a", href=True)
            cols = row.find_all(["td", "th"])
            if not link or len(cols) < 2:
                continue
            title = _clean(link.get_text(" "))
            if not title:
                continue
            url = urljoin("https://www.aph.gov.au", link["href"])
            status = _clean(cols[-1].get_text(" "))
            bills.append(Bill(
                id=_id_from_url(url, str(index)),
                jurisdiction=self.jurisdiction,
                title=title,
                source_url=url,
                status=status,
                house=_clean(cols[1].get_text(" ")) if len(cols) > 1 else None,
                progress=_progress(status),
            ))
        if not bills:
            raise ParseError("Federal bill table not found")
        return bills

    def _hydrate(self, bill: Bill) -> Bill:
        soup = self._html(bill.source_url)
        summary = soup.find(id=re.compile("summaryPanel", re.I)) or soup.find(class_=re.compile("summary", re.I))
        if summary:
            bill.summary = _clean(summary.get_text(" "))
        sponsor = soup.find(id=re.compile("sponsorPanel", re.I))
        if sponsor:
            bill.sponsor = _clean(sponsor.get_text(" "))
        portfolio = soup.find(id=re.compile("portfolioPanel", re.I))
        if portfolio:
            bill.portfolio = _clean(portfolio.get_text(" "))
        bill.documents = self._documents(soup, bill.source_url)
        return bill
