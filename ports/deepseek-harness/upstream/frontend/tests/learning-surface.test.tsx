import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import ArtifactFrame from "../src/ArtifactFrame";
vi.mock("../src/workspace-api", () => ({workspaceApi:vi.fn(),workspaceUrl:(path:string)=>path,versionQuery:()=>"?version=v1"}));
afterEach(cleanup);
it("changes presentation without remounting or navigating the interactive document", () => {
  render(<ArtifactFrame kind="studio" id="a" version="v1" title="同一讲解" onQuestion={vi.fn()} report={vi.fn()} />);
  const frame = screen.getByTitle("同一讲解");
  const src = frame.getAttribute("src");
  fireEvent.click(screen.getByRole("button", {name:"展开讲解"}));
  expect(screen.getByTitle("同一讲解")).toBe(frame);
  fireEvent.click(screen.getByRole("button", {name:"返回工作台"}));
  expect(screen.getByTitle("同一讲解")).toBe(frame);
  expect(frame.getAttribute("src")).toBe(src);
});
