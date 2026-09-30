import { useState } from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import PdfReader from "../src/PdfReader";
const mock = vi.hoisted(() => ({
  count: 3,
  fail: -1,
  calls: [] as number[][],
}));
vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: {},
  TextLayer: class {
    render() {
      return Promise.resolve();
    }
    cancel() {}
  },
  getDocument: () => {
    const count = mock.count;
    return {
      destroy: vi.fn(),
      promise: Promise.resolve({
        numPages: count,
        getPageLabels: async () => null,
        getPage: async (page: number) => {
          mock.calls.push([count, page]);
          if (page > count || page === mock.fail)
            throw new Error("Page unavailable");
          return {
            getViewport: () => ({ width: 600, height: 800 }),
            render: () => ({ promise: Promise.resolve(), cancel: vi.fn() }),
            getTextContent: async () => ({ items: [1] }),
          };
        },
      }),
    };
  },
}));
function Reader({ version }: { version: string }) {
  const [page, setPage] = useState(2);
  return (
    <PdfReader
      paper={{
        id: "p",
        revision: 1,
        source_version: version,
        page_count: mock.count,
      }}
      page={page}
      setPage={setPage}
      onAnchor={vi.fn()}
      focusAnchor={null}
    />
  );
}
beforeEach(() => {
  mock.count = 3;
  mock.fail = -1;
  mock.calls = [];
});
afterEach(cleanup);
it("bounds the page when replacing a PDF with a shorter version", async () => {
  const view = render(<Reader version="old" />);
  await waitFor(() => expect(mock.calls).toContainEqual([3, 3]));
  mock.count = 1;
  view.rerender(<Reader version="new" />);
  await waitFor(() => expect(mock.calls).toContainEqual([1, 1]));
  expect(mock.calls).not.toContainEqual([1, 3]);
  expect(document.querySelector("canvas")).toBeTruthy();
});
it("can render another page after a page-rendering failure", async () => {
  mock.fail = 3;
  render(<Reader version="old" />);
  expect(await screen.findByRole("alert")).toBeTruthy();
  fireEvent.click(screen.getByLabelText("上一页"));
  await waitFor(() => expect(mock.calls).toContainEqual([3, 2]));
  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  expect(document.querySelector("canvas")).toBeTruthy();
});
