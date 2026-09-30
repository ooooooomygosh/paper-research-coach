import { useState } from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  act,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import PdfNavigation from "../src/PdfNavigation";

afterEach(cleanup);
function documentWithText() {
  return {
    numPages: 3,
    getOutline: async () => [
      {
        title: "Evidence",
        dest: "evidence",
        items: [{ title: "Broken", dest: "missing" }],
      },
    ],
    getDestination: async (name: string) =>
      name === "evidence" ? [{ num: 8 }, "Fit"] : null,
    getPageIndex: async () => 1,
    getPage: vi.fn(async (n: number) => ({
      getTextContent: async () => ({
        items:
          n === 3
            ? []
            : [
                {
                  str:
                    n === 1
                      ? "Introduction to predictions"
                      : "Budget-matched evidence separates two explanations",
                },
              ],
      }),
    })),
  } as any;
}
it("navigates real outline destinations and returns after a search jump", async () => {
  const doc = documentWithText();
  function Reader() {
    const [page, setPage] = useState(0);
    return (
      <>
        <span>Current page {page}</span>
        <PdfNavigation
          doc={doc}
          sourceKey="paper:v1"
          page={page}
          onNavigate={setPage}
        />
      </>
    );
  }
  render(<Reader />);
  fireEvent.click(screen.getByText("目录与搜索"));
  fireEvent.click(await screen.findByText("Evidence · 第 2 页"));
  expect(screen.getByText("Current page 1")).toBeTruthy();
  expect(
    (screen.getByText("Broken · 无可用页码") as HTMLButtonElement).disabled,
  ).toBe(true);
  fireEvent.click(screen.getByLabelText("返回上一阅读位置"));
  expect(screen.getByText("Current page 0")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("搜索 PDF 正文"), {
    target: { value: "budget-MATCHED" },
  });
  fireEvent.click(screen.getByRole("button", { name: "搜索", exact: true }));
  await screen.findByText("找到 1 个命中页 · 已搜索 3 页");
  expect(screen.getByText(/1 页没有文字层/)).toBeTruthy();
  fireEvent.click(screen.getByText("PDF 第 2 页"));
  expect(screen.getByText("Current page 1")).toBeTruthy();
  fireEvent.click(screen.getByLabelText("返回上一阅读位置"));
  expect(screen.getByText("Current page 0")).toBeTruthy();
});

it("does not carry old search results or history into a replaced PDF", async () => {
  let release: any;
  const first = documentWithText();
  first.getPage = () =>
    new Promise((resolve) => {
      release = () =>
        resolve({
          getTextContent: async () => ({ items: [{ str: "OLD result" }] }),
        });
    });
  const view = render(
    <PdfNavigation
      doc={first}
      sourceKey="paper:old"
      page={0}
      onNavigate={vi.fn()}
    />,
  );
  fireEvent.click(screen.getByText("目录与搜索"));
  fireEvent.change(screen.getByLabelText("搜索 PDF 正文"), {
    target: { value: "OLD" },
  });
  fireEvent.click(screen.getByRole("button", { name: "搜索", exact: true }));
  await waitFor(() => expect(release).toBeDefined());
  view.rerender(
    <PdfNavigation
      doc={documentWithText()}
      sourceKey="paper:new"
      page={0}
      onNavigate={vi.fn()}
    />,
  );
  await act(async () => release());
  expect(screen.queryByText("OLD result")).toBeNull();
  expect(
    (screen.getByLabelText("返回上一阅读位置") as HTMLButtonElement).disabled,
  ).toBe(true);
  expect(
    (screen.getByLabelText("搜索 PDF 正文") as HTMLInputElement).value,
  ).toBe("");
});
