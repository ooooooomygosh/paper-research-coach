import type { PDFDocumentProxy, PDFPageProxy } from "pdfjs-dist/legacy/build/pdf.mjs";

type Content = ReturnType<PDFPageProxy["getTextContent"]>;
const MAX_PAGES = 16;
const documents = new WeakMap<PDFDocumentProxy, Map<number, Content>>();

export function pageText(doc: PDFDocumentProxy, index: number, page?: PDFPageProxy): Content {
  let pages = documents.get(doc);
  if (!pages) {
    pages = new Map();
    documents.set(doc, pages);
  }
  const cached = pages.get(index);
  pages.delete(index);
  if (cached) {
    pages.set(index, cached);
    return cached;
  }
  const cache = pages;
  const pending = (page ? page.getTextContent() : doc.getPage(index + 1).then(p => p.getTextContent()))
    .catch(error => {
      if (cache.get(index) === pending) cache.delete(index);
      throw error;
    });
  cache.set(index, pending);
  if (cache.size > MAX_PAGES) cache.delete(cache.keys().next().value!);
  return pending;
}
