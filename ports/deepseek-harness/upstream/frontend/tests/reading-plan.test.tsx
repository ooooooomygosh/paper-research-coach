import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import ReadingPlan from "../src/ReadingPlan";
import { api } from "../src/api";
vi.mock("../src/api", async (original) => ({ ...(await original<any>()), api: vi.fn() }));
afterEach(cleanup);
it("jumps directly to evidence without inventing completed steps or invoking the model", async () => {
  vi.mocked(api).mockResolvedValue({});
  const refresh = vi.fn();
  render(<ReadingPlan paperId="p" onChange={refresh} plan={{revision:2, depth:"understand", current_phase:"orient", current_task:0, status:"active", phases:[{id:"orient",label:"判断是否值得读",tasks:["one task"]},{id:"evidence",label:"核查证据与边界",tasks:[]}]}} />);
  fireEvent.click(screen.getByRole("button", {name:"核查证据与边界"}));
  await waitFor(() => expect(refresh).toHaveBeenCalled());
  expect(api).toHaveBeenCalledWith("reading/p/plan", expect.objectContaining({action:"navigate", phase:"evidence", expected_revision:2}));
  expect(vi.mocked(api).mock.calls.every(([path]) => !path.includes("coach/send"))).toBe(true);
});
