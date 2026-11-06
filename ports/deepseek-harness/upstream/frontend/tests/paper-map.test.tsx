import { expect, it } from "vitest";
import { sectionChip, sectionsAt } from "../src/paper-map";

const map = {
  outline: [
    { title: "2 Method", page_index: 1, depth: 0 },
    { title: "2.1 Trigger rule", page_index: 1, depth: 1 },
    { title: "3 Experiments", page_index: 3, depth: 0 },
  ],
};

it("names what carries over a page and what starts on it", () => {
  expect(sectionsAt(map, 0)).toEqual({ carried: "", starting: [] });
  expect(sectionsAt(map, 1)).toEqual({ carried: "", starting: ["2 Method", "2.1 Trigger rule"] });
  expect(sectionsAt(map, 2)).toEqual({ carried: "2.1 Trigger rule", starting: [] });
  expect(sectionsAt(map, 3)).toEqual({ carried: "2.1 Trigger rule", starting: ["3 Experiments"] });
});

it("makes a short chip, with the whole story in its tooltip, and nothing when the structure is unknown", () => {
  expect(sectionChip(map, 0)).toBeNull();
  expect(sectionChip(null, 2)).toBeNull();
  expect(sectionChip({}, 2)).toBeNull();
  expect(sectionChip(map, 2)!.text).toBe("2.1 Trigger rule");
  expect(sectionChip(map, 1)!.text).toBe("本页开始 2.1 Trigger rule");
  const both = sectionChip(map, 3)!;
  expect(both.text).toBe("2.1 Trigger rule → 3 Experiments");
  expect(both.title).toContain("承接：2.1 Trigger rule");
  expect(both.title).toContain("自动识别，可能不全");
  expect(sectionChip({ outline: [{ title: "A".repeat(80), page_index: 0, depth: 0 }] }, 1)!.text.length).toBeLessThanOrEqual(30);
});
