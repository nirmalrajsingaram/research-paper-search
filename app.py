"""Small multi-source research paper search demo."""

import json
import html
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
PAGE_SIZE = 10
ATOM = "{http://www.w3.org/2005/Atom}"


def fetch(url, user_agent):
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=15) as response:
        return response.read()


def search_arxiv(query, page):
    params = urllib.parse.urlencode({
        "search_query": f'all:"{query}"', "start": (page - 1) * PAGE_SIZE,
        "max_results": PAGE_SIZE, "sortBy": "relevance",
    })
    root = ET.fromstring(fetch(f"https://export.arxiv.org/api/query?{params}", "PaperSearchDemo/1.0"))
    papers = []
    for entry in root.findall(f"{ATOM}entry"):
        links = entry.findall(f"{ATOM}link")
        paper_url = next((link.get("href", "") for link in links if link.get("rel") == "alternate"), "")
        pdf_url = next((link.get("href", "") for link in links if link.get("title") == "pdf"), "")
        papers.append({
            "title": " ".join(entry.findtext(f"{ATOM}title", "").split()),
            "authors": ", ".join(a.findtext(f"{ATOM}name", "") for a in entry.findall(f"{ATOM}author")),
            "year": entry.findtext(f"{ATOM}published", "")[:4],
            "abstract": " ".join(entry.findtext(f"{ATOM}summary", "").split()),
            "url": paper_url, "pdf_url": pdf_url, "source": "arXiv",
        })
    total = int(root.findtext("{http://a9.com/-/spec/opensearch/1.1/}totalResults", "0"))
    return papers, total > page * PAGE_SIZE


def openalex_abstract(index):
    if not index:
        return ""
    words = {}
    for word, positions in index.items():
        for position in positions:
            words[position] = word
    return " ".join(words[position] for position in sorted(words))


def search_openalex(query, page):
    params = urllib.parse.urlencode({"search": query, "per-page": PAGE_SIZE, "page": page, "sort": "relevance_score:desc"})
    payload = json.loads(fetch(f"https://api.openalex.org/works?{params}", "PaperSearchDemo/1.0 (local sample)"))
    papers = []
    for work in payload.get("results", []):
        locs = [work.get("best_oa_location"), work.get("primary_location"), *(work.get("locations") or [])]
        pdf = next((loc.get("pdf_url") for loc in locs if loc and loc.get("pdf_url")), "")
        doi = work.get("doi") or work.get("id", "")
        papers.append({
            "title": work.get("display_name") or "Untitled",
            "authors": ", ".join(item.get("author", {}).get("display_name", "") for item in work.get("authorships", [])),
            "year": str(work.get("publication_year") or ""),
            "abstract": openalex_abstract(work.get("abstract_inverted_index")),
            "url": doi, "pdf_url": pdf, "source": "OpenAlex",
        })
    meta = payload.get("meta", {})
    return papers, (page * PAGE_SIZE < meta.get("count", 0))


def render_index(query, page, selected):
    query = query.strip()
    page = max(1, page)
    if not selected:
        selected = ["arxiv", "openalex"]
    selected = [source for source in selected if source in {"arxiv", "openalex"}]
    papers, errors, more_pages = [], [], False
    if query and selected:
        searches = {"arxiv": search_arxiv, "openalex": search_openalex}
        with ThreadPoolExecutor(max_workers=len(selected)) as pool:
            futures = {name: pool.submit(searches[name], query, page) for name in selected}
            for name, future in futures.items():
                try:
                    found, has_next = future.result()
                    papers.extend(found)
                    more_pages = more_pages or has_next
                except Exception as exc:
                    errors.append(f"{name.title()} could not be searched: {exc}")
        papers.sort(key=lambda paper: paper["year"], reverse=True)
    e = html.escape
    source_checks = "".join(
        f'<label><input type="checkbox" name="source" value="{name}" {"checked" if name in selected else ""}> {label}</label>'
        for name, label in (("arxiv", "arXiv"), ("openalex", "OpenAlex"))
    )
    result_html = ""
    if query:
        result_html += f'<section class="results"><div class="result-heading"><div><p class="kicker">SEARCH RESULTS</p><h2>“{e(query)}”</h2></div><span class="count">{len(papers)} papers · page {page}</span></div>'
        if errors:
            result_html += '<div class="notice">' + "".join(f"<p>{e(message)}</p>" for message in errors) + "</div>"
        if papers:
            result_html += '<div class="table-scroll"><table><thead><tr><th>Paper</th><th>Authors</th><th>Year</th><th>Source</th><th>PDF</th></tr></thead><tbody>'
            for paper in papers:
                abstract = f'<details><summary>Abstract</summary><p>{e(paper["abstract"])}</p></details>' if paper["abstract"] else ""
                pdf = f'<a class="pdf" href="{e(paper["pdf_url"])}" target="_blank" rel="noopener noreferrer">View PDF ↗</a>' if paper["pdf_url"] else '<span class="muted">—</span>'
                result_html += (f'<tr><td class="paper-title"><a href="{e(paper["url"])}" target="_blank" rel="noopener noreferrer">{e(paper["title"])} ↗</a>{abstract}</td>'
                                f'<td class="authors">{e(paper["authors"] or "—")}</td><td>{e(paper["year"] or "—")}</td>'
                                f'<td><span class="source">{e(paper["source"])}</span></td><td>{pdf}</td></tr>')
            result_html += '</tbody></table></div><nav class="pagination" aria-label="Search results pages">'
            prev_link = urllib.parse.urlencode([( "q", query), *(("source", s) for s in selected), ("page", page - 1)])
            next_link = urllib.parse.urlencode([( "q", query), *(("source", s) for s in selected), ("page", page + 1)])
            result_html += f'<a href="/?{prev_link}">← Previous</a>' if page > 1 else '<span></span>'
            result_html += f'<span class="page">Page {page}</span>'
            result_html += f'<a class="next" href="/?{next_link}">Next →</a>' if more_pages else '<span></span>'
            result_html += '</nav>'
        elif not errors:
            result_html += '<div class="empty"><strong>No papers found on this page.</strong><p>Try another topic or check the selected sources.</p></div>'
        result_html += '</section>'
    else:
        result_html = '<section class="welcome"><span class="spark">✳</span><div><h2>Start with a research topic</h2><p>Results include publication details, abstracts, source links, and available PDFs.</p></div></section>'
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Paper Finder</title><link rel="stylesheet" href="/static/style.css"></head><body><main class="shell"><header class="heading"><div class="brand">P<span>F</span></div><div><p class="kicker">OPEN RESEARCH DISCOVERY</p><h1>Paper Finder</h1><p class="subhead">Search across scholarly sources in one place.</p></div></header><form class="search" method="get" action="/"><label class="sr-only" for="q">Research topic</label><input id="q" type="search" name="q" value="{e(query)}" placeholder="Try ‘climate modeling’ or ‘large language models’" required><fieldset><legend>Sources</legend>{source_checks}</fieldset><button type="submit">Search papers <span aria-hidden="true">↗</span></button></form>{result_html}<footer>Paper Finder <span>Sample project · arXiv + OpenAlex</span></footer></main></body></html>'''


class PaperFinderHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urllib.parse.urlsplit(self.path)
        if path.path == "/static/style.css":
            css_path = Path(__file__).parent / "static" / "style.css"
            body, content_type = css_path.read_bytes(), "text/css; charset=utf-8"
        elif path.path == "/":
            args = urllib.parse.parse_qs(path.query)
            try:
                page = int(args.get("page", ["1"])[0])
            except ValueError:
                page = 1
            body = render_index(args.get("q", [""])[0], page, args.get("source", [] )).encode("utf-8")
            content_type = "text/html; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("[paper-finder] " + fmt % args)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5051"))
    server = ThreadingHTTPServer(("127.0.0.1", port), PaperFinderHandler)
    print(f"Paper Finder is running at http://127.0.0.1:{port}")
    server.serve_forever()
