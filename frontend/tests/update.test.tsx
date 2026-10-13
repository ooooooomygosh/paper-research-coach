import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { UpdateRow, UpdateSettings, useUpdate } from "../src/UpdateNotice";
import { api } from "../src/api";

vi.mock("../src/api", async (original) => ({ ...(await original<any>()), api: vi.fn() }));

function Probe({ variant = "row" as "row" | "banner" }) {
  const update = useUpdate(true);
  return <UpdateRow update={update} variant={variant} />;
}
const newer = { current: "2.0.0rc10", available: true, latest: "2.0.0rc11", notes_url: "https://example.test/notes", job: { state: "idle", message: "" } };
let reload: ReturnType<typeof vi.fn>;
beforeEach(() => {
  reload = vi.fn();
  vi.stubGlobal("location", { ...window.location, reload });
});
afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

it("says nothing when there is no newer version, or when checking is turned off", async () => {
  vi.mocked(api).mockResolvedValue({ current: "2.0.0rc10", available: false, job: { state: "idle", message: "" } });
  const { container } = render(<Probe />);
  await waitFor(() => expect(api).toHaveBeenCalledWith("update"));
  expect(container.textContent).toBe("");
  cleanup();
  vi.mocked(api).mockResolvedValue({ ...newer, disabled: true });
  const off = render(<Probe />);
  await waitFor(() => expect(api).toHaveBeenCalledTimes(2));
  expect(off.container.textContent).toBe("");
});

it("offers one quiet update with a link to what changed", async () => {
  vi.mocked(api).mockResolvedValue(newer);
  render(<Probe />);
  expect(await screen.findByText("2.0.0rc11")).toBeTruthy();
  expect(screen.getByRole("link", { name: "更新内容" }).getAttribute("href")).toBe("https://example.test/notes");
  expect(screen.getByRole("button", { name: "更新并重启" })).toBeTruthy();
});

it("updates, waits through the restart, and loads the new version's page", async () => {
  let calls = 0;
  vi.mocked(api).mockImplementation(async (path: string) => {
    if (path === "update/apply") return { state: "running", message: "" };
    if (path === "update") {
      calls += 1;
      if (calls === 1) return newer; // the first look on page load
      if (calls === 2) return { ...newer, job: { state: "restarting", message: "已更新到 2.0.0rc11，正在重新启动…" } };
      if (calls === 3) throw new Error("service is restarting");
      return { current: "2.0.0rc11", available: false, job: { state: "idle", message: "" } };
    }
    return {};
  });
  vi.useFakeTimers({ shouldAdvanceTime: true });
  render(<Probe />);
  fireEvent.click(await screen.findByRole("button", { name: "更新并重启" }));
  expect(vi.mocked(api)).toHaveBeenCalledWith("update/apply", {});
  for (let i = 0; i < 4; i++) await act(async () => void (await vi.advanceTimersByTimeAsync(1600)));
  await waitFor(() => expect(reload).toHaveBeenCalledTimes(1));
});

it("shows a plain failure message and lets the reader retry", async () => {
  let polls = 0;
  vi.mocked(api).mockImplementation(async (path: string) => {
    if (path === "update/apply") return { state: "running", message: "" };
    polls += 1;
    return polls === 1 ? newer : { ...newer, job: { state: "error", message: "安装包的校验值不符，已停止更新。" } };
  });
  vi.useFakeTimers({ shouldAdvanceTime: true });
  render(<Probe />);
  fireEvent.click(await screen.findByRole("button", { name: "更新并重启" }));
  await act(async () => void (await vi.advanceTimersByTimeAsync(1600)));
  expect(await screen.findByText("安装包的校验值不符，已停止更新。")).toBeTruthy();
  expect(screen.getByRole("button", { name: "重试更新" })).toBeTruthy();
  expect(reload).not.toHaveBeenCalled();
});

it("the banner can be put off for this version, and stays off after a reload", async () => {
  vi.mocked(api).mockResolvedValue(newer);
  const first = render(<Probe variant="banner" />);
  fireEvent.click(await screen.findByRole("button", { name: "稍后" }));
  expect(first.container.textContent).toBe("");
  first.unmount();
  const second = render(<Probe variant="banner" />);
  await waitFor(() => expect(api).toHaveBeenCalledTimes(2));
  expect(second.container.textContent).toBe("");
  // The quiet row elsewhere is not affected.
  second.unmount();
  render(<Probe />);
  expect(await screen.findByText("2.0.0rc11")).toBeTruthy();
});

it("after a background install offers only a short reload, and the switch turns installs off", async () => {
  vi.mocked(api).mockImplementation(async (path: string, body?: any) => {
    if (path === "update") return { ...newer, auto: true, job: { state: "ready", message: "已装好", version: "2.0.0rc11" } };
    if (path === "update/settings") return { auto: body.auto };
    return {};
  });
  function Settings() {
    const update = useUpdate(true);
    return <UpdateSettings update={update} />;
  }
  render(<Settings />);
  expect(await screen.findByRole("button", { name: "重新载入（约 5 秒）" })).toBeTruthy();
  const box = screen.getByRole("checkbox", { name: /自动安装新版本/ }) as HTMLInputElement;
  expect(box.checked).toBe(true);
  fireEvent.click(box);
  await waitFor(() => expect(api).toHaveBeenCalledWith("update/settings", { auto: false }));
  await waitFor(() => expect((screen.getByRole("checkbox", { name: /自动安装新版本/ }) as HTMLInputElement).checked).toBe(false));
});
