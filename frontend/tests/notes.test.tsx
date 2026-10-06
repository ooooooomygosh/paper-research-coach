import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import Notes from "../src/Notes";
import { put, ApiError } from "../src/api";
vi.mock("../src/api", async (original) => ({
  ...(await original<any>()),
  put: vi.fn(),
  api: vi.fn(),
}));
const props = {
  paper: { id: "p", revision: 1 },
  notes: [],
  anchor: null,
  onLocate: vi.fn(),
  refresh: vi.fn(),
  report: vi.fn(),
};
const write = vi.mocked(put);
const saved = (_: string, data: any) =>
  Promise.resolve({ ...data, revision: (data.revision || 0) + 1 });
beforeEach(() => {
  localStorage.clear();
  vi.useFakeTimers();
  write.mockReset().mockImplementation(saved);
});
afterEach(async () => {
  await act(async () => cleanup());
  vi.clearAllTimers();
  vi.useRealTimers();
});
const tick = (ms: number) =>
  act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });

it("selecting a location waits for words instead of claiming an ongoing save", async () => {
  render(
    <Notes {...props} anchor={{ page_index: 0, quote: "Selected words" }} />,
  );
  await tick(600);
  expect(write).not.toHaveBeenCalled();
  expect(screen.getByText("位置已选，输入后自动保存")).toBeTruthy();
  expect(screen.queryByText("正在保存…")).toBeNull();
});

it("retries the pending words even if the current editor was cleared", async () => {
  write.mockRejectedValueOnce(new TypeError("offline"));
  render(<Notes {...props} />);
  fireEvent.change(screen.getByLabelText("记录想法"), {
    target: { value: "pending words" },
  });
  await tick(450);
  const first = write.mock.calls[0];
  fireEvent.change(screen.getByLabelText("记录想法"), {
    target: { value: "" },
  });
  await tick(600);
  expect(write).toHaveBeenCalledTimes(2);
  expect(write.mock.calls[1]).toEqual(first);
  expect(localStorage.getItem("prc-draft-p-operation")).toBeNull();
  expect(screen.getByText("内容为空，原笔记保持不变")).toBeTruthy();
  expect((screen.getByLabelText("记录想法") as HTMLTextAreaElement).value).toBe(
    "",
  );
});

it("retries a disconnected save with exactly the same transaction", async () => {
  write.mockRejectedValueOnce(new TypeError("offline"));
  render(<Notes {...props} />);
  fireEvent.change(screen.getByLabelText("记录想法"), {
    target: { value: "  原话\nwith spaces  " },
  });
  await tick(450);
  const first = write.mock.calls[0];
  expect(localStorage.getItem("prc-draft-p-operation")).toContain(first[2]);
  await tick(1000);
  expect(write).toHaveBeenCalledTimes(2);
  expect(write.mock.calls[1]).toEqual(first);
  expect(localStorage.getItem("prc-draft-p-operation")).toBeNull();
  expect(screen.getByText("已保存 · 等待讨论")).toBeTruthy();
});

it("restores an interrupted transaction after a page reload", async () => {
  const value = {
    id: "draft",
    paper_id: "p",
    content: "未完成的保存",
    author: "user",
    provenance: "USER",
    revision: 0,
    anchor: null,
  };
  localStorage.setItem("prc-draft-p", JSON.stringify(value));
  localStorage.setItem(
    "prc-draft-p-operation",
    JSON.stringify({ value, op: "same-operation" }),
  );
  render(<Notes {...props} />);
  await tick(100);
  expect(write).toHaveBeenCalledWith("note", value, "same-operation");
  expect(JSON.parse(localStorage.getItem("prc-draft-p")!).revision).toBe(1);
});

it("keeps words typed while switching to a new thought", async () => {
  let complete!: (value: any) => void;
  write.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        complete = resolve;
      }),
  );
  render(<Notes {...props} />);
  fireEvent.change(screen.getByLabelText("记录想法"), {
    target: { value: "first words" },
  });
  fireEvent.click(screen.getByText("新想法"));
  fireEvent.change(screen.getByLabelText("记录想法"), {
    target: { value: "later words must survive" },
  });
  await act(async () => complete({ ...write.mock.calls[0][1], revision: 1 }));
  await tick(500);
  expect((screen.getByLabelText("记录想法") as HTMLTextAreaElement).value).toBe(
    "later words must survive",
  );
  expect(write.mock.calls.at(-1)![1].content).toBe("later words must survive");
  expect(JSON.parse(localStorage.getItem("prc-draft-p")!).content).toBe(
    "later words must survive",
  );
});

it("new words on a discussed note return to the discussion queue", async () => {
  const note = {
    id: "old",
    paper_id: "p",
    content: "old thought",
    author: "user",
    provenance: "USER",
    revision: 3,
    anchor: null,
    discussed: true,
  };
  localStorage.setItem("prc-draft-p", JSON.stringify(note));
  render(<Notes {...props} notes={[note]} />);
  fireEvent.change(screen.getByLabelText("记录想法"), {
    target: { value: "a new counterargument" },
  });
  await tick(450);
  expect(write.mock.calls[0][1].discussed).toBe(false);
});

it("does not blindly retry or overwrite a revision conflict", async () => {
  write.mockRejectedValue(new ApiError("Revision changed", 409));
  render(<Notes {...props} />);
  fireEvent.change(screen.getByLabelText("记录想法"), {
    target: { value: "keep this draft" },
  });
  await tick(450);
  await tick(31000);
  expect(write).toHaveBeenCalledTimes(1);
  expect(screen.getByText("保留为独立笔记")).toBeTruthy();
  expect(JSON.parse(localStorage.getItem("prc-draft-p")!).content).toBe(
    "keep this draft",
  );
});

it("does not change note identity while an automatic retry is in flight", async () => {
  let complete!: (value: any) => void;
  write.mockRejectedValueOnce(new TypeError("offline")).mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        complete = resolve;
      }),
  );
  render(<Notes {...props} />);
  fireEvent.change(screen.getByLabelText("记录想法"), {
    target: { value: "original pending" },
  });
  await tick(1450);
  const original = JSON.parse(localStorage.getItem("prc-draft-p")!);
  fireEvent.click(screen.getByText("保留为独立笔记"));
  expect(JSON.parse(localStorage.getItem("prc-draft-p")!).id).toBe(original.id);
  await act(async () => complete({ ...original, revision: 1 }));
  expect(JSON.parse(localStorage.getItem("prc-draft-p")!).revision).toBe(1);
});

it("an unmounted save cannot overwrite the newer mounted draft", async () => {
  let oldComplete!: (value: any) => void;
  write.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        oldComplete = resolve;
      }),
  );
  const old = render(<Notes {...props} />);
  fireEvent.change(screen.getByLabelText("记录想法"), {
    target: { value: "v1" },
  });
  await tick(450);
  const first = { ...write.mock.calls[0][1], revision: 1 };
  old.unmount();
  render(<Notes {...props} />);
  await tick(100);
  fireEvent.change(screen.getByLabelText("记录想法"), {
    target: { value: "v2 persisted" },
  });
  await tick(450);
  fireEvent.change(screen.getByLabelText("记录想法"), {
    target: { value: "v3 still typing" },
  });
  const before = localStorage.getItem("prc-draft-p");
  await act(async () => oldComplete(first));
  expect(localStorage.getItem("prc-draft-p")).toBe(before);
  expect((screen.getByLabelText("记录想法") as HTMLTextAreaElement).value).toBe(
    "v3 still typing",
  );
});

it("restores the same region after a coach comment without saving a stale revision", async () => {
  const note = {
    id: "region",
    paper_id: "p",
    content: "my region thought",
    author: "user",
    provenance: "USER",
    revision: 1,
    anchor: {
      paper_id: "p",
      source_version: "v1",
      page_index: 0,
      rects: [[1, 2, 3, 4]],
      status: "verified",
    },
  };
  const latest = {
    ...note,
    revision: 2,
    discussed: true,
    anchor: {
      ...note.anchor,
      page_label: "",
      section: "",
      figure: "",
      quote: "",
    },
  };
  localStorage.setItem("prc-draft-p", JSON.stringify(note));
  localStorage.setItem(
    "prc-draft-p-operation",
    JSON.stringify({ value: note, op: "stale-metadata" }),
  );
  render(<Notes {...props} notes={[latest]} />);
  await tick(500);
  expect(write).not.toHaveBeenCalled();
  expect(screen.getByText("已保存 · 已讨论")).toBeTruthy();
  expect(localStorage.getItem("prc-draft-p-operation")).toBeNull();
  expect(JSON.parse(localStorage.getItem("prc-draft-p")!).revision).toBe(2);
});

it("browsing a new selection never silently moves an existing note's source", async () => {
  const original = {
    paper_id: "p",
    source_version: "v",
    page_index: 0,
    quote: "original",
    status: "verified",
  };
  const next = { ...original, page_index: 1, quote: "new selection" };
  const note = {
    id: "existing",
    paper_id: "p",
    content: "my original thought",
    author: "user",
    provenance: "USER",
    revision: 2,
    anchor: original,
  };
  localStorage.setItem("prc-draft-p", JSON.stringify(note));
  const mounted = render(<Notes {...props} notes={[note]} />);
  await tick(500);
  write.mockClear();
  mounted.rerender(<Notes {...props} notes={[note]} anchor={next} />);
  await tick(600);
  expect(write).not.toHaveBeenCalled();
  expect(JSON.parse(localStorage.getItem("prc-draft-p")!).anchor).toEqual(
    original,
  );
  fireEvent.click(screen.getByText("将此笔记的出处改为当前选区"));
  await tick(500);
  expect(write.mock.calls.at(-1)![1].anchor).toEqual(next);
});

it("shows a kept highlight as the paper's words, not mine, and does not count it as pending", async () => {
  const anchor = {
    paper_id: "p",
    page_index: 1,
    quote: "No error bars are reported.",
  };
  render(
    <Notes
      {...props}
      notes={[
        {
          id: "m",
          revision: 1,
          author: "user",
          content: "No error bars are reported.",
          anchor,
          discussed: false,
        },
        {
          id: "t",
          revision: 1,
          author: "user",
          content: "可能只是噪声",
          anchor,
          discussed: false,
        },
      ]}
    />,
  );
  expect(screen.getByText("原文标记")).toBeTruthy();
  expect(screen.getAllByText("我的原话")).toHaveLength(1);
  expect(screen.getByText("1 条待讨论")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "写下想法" }));
  await tick(50);
  expect(write).not.toHaveBeenCalledWith(
    "note",
    expect.objectContaining({ id: "m" }),
    expect.anything(),
  );
});
