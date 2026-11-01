# Paper Finder

A small Python sample that searches arXiv and OpenAlex for research papers. Results from the selected providers appear together in a table with authors, year, abstract, source, and an available PDF link. Previous and next links preserve the search query and provider selection.

## Run locally

Requires Python 3.9+ and an internet connection to the public arXiv and OpenAlex APIs. No package installation is needed.

```bash
cd research-paper-search
./start.sh
```

Open <http://127.0.0.1:5051>. Search is performed live, so no API keys or database are needed. OpenAlex may not provide an abstract or open PDF for every paper. Set `PORT` to use another port.

## Sources

- arXiv API: <https://export.arxiv.org/api>
- OpenAlex Works API: <https://api.openalex.org/works>
