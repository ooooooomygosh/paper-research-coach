import { useEffect, useRef, useState } from "react";
import type { PDFDocumentProxy } from "pdfjs-dist/legacy/build/pdf.mjs";

type Viewer = {
  initializedPromise: Promise<void>;
  initialBookmark: string;
  _annotationStorageModified?: boolean;
  _saveInProgress?: boolean;
  open(options: { data: Uint8Array; filename: string }): Promise<void>;
};

export default function AdvancedPdfViewer({
  document, filename, page, onClose,
}: {
  document: PDFDocumentProxy;
  filename: string;
  page: number;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const frame = useRef<HTMLIFrameElement>(null);
  const viewer = useRef<Viewer | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);
  const [status, setStatus] = useState("正在打开高级 PDF 工具…");

  useEffect(() => {
    dialog.current?.showModal();
  }, []);

  useEffect(() => {
    if (!loaded) return;
    let closed = false;
    async function open() {
      try {
        const viewerWindow = frame.current?.contentWindow as (Window & { PDFViewerApplication?: Viewer }) | null;
        const application = viewerWindow?.PDFViewerApplication;
        if (!application) throw new Error("PDF.js viewer unavailable");
        viewer.current = application;
        await application.initializedPromise;
        if (closed) return;
        const data = await document.getData();
        if (closed) return;
        application.initialBookmark = `page=${page + 1}`;
        await application.open({ data, filename });
        if (!closed) setStatus("");
      } catch {
        if (!closed) setStatus("高级 PDF 工具未能打开当前文档。");
      }
    }
    void open();
    return () => { closed = true; };
  }, [loaded, document, filename, page]);

  function requestClose() {
    if (viewer.current?._annotationStorageModified || viewer.current?._saveInProgress) {
      setConfirmClose(true);
    } else onClose();
  }

  return <dialog ref={dialog} className="advanced-pdf-dialog" aria-label="高级 PDF 工具"
    onCancel={(event) => { event.preventDefault(); requestClose(); }}>
    <header>
      <div>
        <strong>高级 PDF 工具</strong>
        <p>在此视图填写表单、编辑或打印。用“保存”下载副本。工作台批注可在阅读器内另行导出。</p>
      </div>
      <button type="button" onClick={requestClose}>返回阅读</button>
    </header>
    {confirmClose && <div className="advanced-pdf-confirm" role="alert">
      <p>当前有修改。要保留，请先在工具栏保存副本。</p>
      <button type="button" onClick={() => setConfirmClose(false)}>继续编辑</button>
      <button type="button" onClick={onClose}>放弃修改并返回</button>
    </div>}
    {status && <p role="status">{status}</p>}
    <iframe ref={frame} title="PDF.js 高级工具" referrerPolicy="no-referrer"
      src={import.meta.env.BASE_URL + "pdf-viewer/web/viewer.html"} onLoad={() => setLoaded(true)} />
  </dialog>;
}
