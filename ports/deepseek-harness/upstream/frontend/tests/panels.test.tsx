import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { Lineage, Ideas } from "../src/Panels";
import { api, put } from "../src/api";
vi.mock("../src/api", async (original) => ({
  ...(await original<any>()),
  put: vi.fn(),
  api: vi.fn(),
}));
const paper = {
  id: "p",
  revision: 1,
  title: "Paper",
  comparison: { problem: "initial" },
};
beforeEach(() => {
  vi.mocked(api).mockReset().mockResolvedValue([]);
  vi.mocked(put).mockReset().mockRejectedValue(new Error("Revision changed"));
});
afterEach(cleanup);
it("keeps an edited comparison tied to the revision the learner saw", async () => {
  const props = {
    paper,
    papers: [paper],
    report: vi.fn(),
    refresh: vi.fn(),
    onSelect: vi.fn(),
  };
  const view = render(<Lineage {...props} seq={1} />);
  fireEvent.change(screen.getByLabelText("研究问题"), {
    target: { value: "local words" },
  });
  const newer = {
    ...paper,
    revision: 2,
    comparison: { problem: "host correction" },
  };
  view.rerender(<Lineage {...props} paper={newer} papers={[newer]} seq={2} />);
  fireEvent.click(screen.getByText("保存比较记录"));
  await waitFor(() => expect(put).toHaveBeenCalled());
  expect(vi.mocked(put).mock.calls[0][1]).toMatchObject({
    revision: 1,
    comparison: { problem: "local words" },
  });
  expect((screen.getByLabelText("研究问题") as HTMLTextAreaElement).value).toBe(
    "local words",
  );
});
it("refreshes an untouched comparison when the host updates it", async () => {
  const props = {
    paper,
    papers: [paper],
    report: vi.fn(),
    refresh: vi.fn(),
    onSelect: vi.fn(),
  };
  const view = render(<Lineage {...props} />);
  view.rerender(
    <Lineage
      {...props}
      paper={{
        ...paper,
        revision: 2,
        comparison: { problem: "host correction" },
      }}
    />,
  );
  await waitFor(() =>
    expect(
      (screen.getByLabelText("研究问题") as HTMLTextAreaElement).value,
    ).toBe("host correction"),
  );
});
it("shows ideas written by the host when the event sequence changes", async () => {
  const view = render(<Ideas paper={paper} seq={1} report={vi.fn()} />);
  await waitFor(() => expect(api).toHaveBeenCalledTimes(1));
  vi.mocked(api).mockResolvedValue([
    { id: "idea", title: "New host idea", status: "seed" },
  ]);
  view.rerender(<Ideas paper={{ ...paper }} seq={2} report={vi.fn()} />);
  expect(await screen.findByText("New host idea")).toBeTruthy();
});

it("preserves comparison words entered while the earlier version is saving", async () => {
  let complete!: (value: any) => void;
  vi.mocked(put).mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        complete = resolve;
      }),
  );
  const props = {
    paper,
    papers: [paper],
    report: vi.fn(),
    refresh: vi.fn(),
    onSelect: vi.fn(),
  };
  render(<Lineage {...props} />);
  fireEvent.change(screen.getByLabelText("研究问题"), {
    target: { value: "submitted" },
  });
  fireEvent.click(screen.getByText("保存比较记录"));
  fireEvent.change(screen.getByLabelText("研究问题"), {
    target: { value: "newer words" },
  });
  complete({ ...paper, revision: 2, comparison: { problem: "submitted" } });
  await waitFor(() => expect(props.refresh).toHaveBeenCalled());
  expect((screen.getByLabelText("研究问题") as HTMLTextAreaElement).value).toBe(
    "newer words",
  );
  fireEvent.click(screen.getByText("保存比较记录"));
  await waitFor(() => expect(put).toHaveBeenCalledTimes(2));
  expect(vi.mocked(put).mock.calls[1][1]).toMatchObject({
    revision: 2,
    comparison: { problem: "newer words" },
  });
});

it("ignores an older event response that arrives after the newest ideas", async () => {
  let oldComplete!: (value: any) => void;
  vi.mocked(api).mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        oldComplete = resolve;
      }),
  );
  const view = render(<Ideas paper={paper} seq={1} report={vi.fn()} />);
  vi.mocked(api).mockResolvedValue([
    { id: "new", title: "Latest idea", status: "seed" },
  ]);
  view.rerender(<Ideas paper={paper} seq={2} report={vi.fn()} />);
  expect(await screen.findByText("Latest idea")).toBeTruthy();
  oldComplete([{ id: "old", title: "Old idea", status: "seed" }]);
  await waitFor(() => expect(screen.queryByText("Old idea")).toBeNull());
  expect(screen.getByText("Latest idea")).toBeTruthy();
});
