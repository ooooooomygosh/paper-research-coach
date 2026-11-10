import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, it, expect, vi } from "vitest";
import { useLearningSurface, LearningCompareControls, splitWidth } from "../src/useLearningSurface";
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
function Surface(){const root=useRef<HTMLDivElement>(null);const s=useLearningSurface(root,true);return <div ref={root}><button onClick={()=>s.setCompare(true)}>compare</button><LearningCompareControls surface={s}/></div>}
it("keeps both panes readable at the smallest wide container",()=>{expect(splitWidth(1120,.44)).toBe(492.8);expect(splitWidth(1120,.9)).toBe(496);expect(splitWidth(1120,.1)).toBe(440);});
it("adjusts the actual pane width by keyboard",()=>{vi.stubGlobal("innerWidth",1440);render(<Surface/>);fireEvent.click(screen.getByText("compare"));const split=screen.getByRole("separator");const old=Number(split.getAttribute("aria-valuenow"));fireEvent.keyDown(split,{key:"ArrowRight"});expect(Number(split.getAttribute("aria-valuenow"))).toBeGreaterThan(old);});
it("offers full-width paper and lesson tabs in a narrow container",()=>{vi.stubGlobal("innerWidth",760);render(<Surface/>);fireEvent.click(screen.getByText("compare"));expect(screen.queryByRole("separator")).toBeNull();fireEvent.click(screen.getByRole("button",{name:"论文"}));expect(document.documentElement.getAttribute("data-learning-compare")).toBe("paper");fireEvent.click(screen.getByRole("button",{name:"讲解"}));expect(document.documentElement.getAttribute("data-learning-compare")).toBe("lesson");});
