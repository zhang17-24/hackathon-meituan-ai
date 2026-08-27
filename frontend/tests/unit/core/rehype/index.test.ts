import type { Root } from "hast";
import { describe, expect, it } from "vitest";

import { rehypeSplitWordsIntoSpans } from "@/core/rehype";

function makeParagraphTree(text: string): Root {
  return {
    type: "root",
    children: [
      {
        type: "element",
        tagName: "p",
        properties: {},
        children: [{ type: "text", value: text }],
      },
    ],
  };
}

function paragraphSpans(tree: Root): Array<{
  tagName: string;
  className?: string;
  style?: string;
  value?: string;
}> {
  const p = tree.children[0] as { children?: unknown[] };
  return (p.children ?? []).map((child) => {
    const el = child as {
      tagName?: string;
      properties?: { className?: string; style?: string };
      children?: Array<{ type: string; value?: string }>;
    };
    return {
      tagName: el.tagName ?? "",
      className: el.properties?.className,
      style: el.properties?.style,
      value:
        typeof el.children?.[0]?.value === "string"
          ? el.children[0].value
          : undefined,
    };
  });
}

describe("rehypeSplitWordsIntoSpans", () => {
  it("splits CJK text into per-character spans with staggered fade-in delay", () => {
    const tree = makeParagraphTree("你好");
    rehypeSplitWordsIntoSpans()(tree);

    const spans = paragraphSpans(tree);
    expect(spans).toEqual([
      {
        tagName: "span",
        className: "animate-fade-in",
        style: "animation-delay:0ms",
        value: "你",
      },
      {
        tagName: "span",
        className: "animate-fade-in",
        style: "animation-delay:18ms",
        value: "好",
      },
    ]);
  });

  it("caps the per-character animation delay for long messages", () => {
    const tree = makeParagraphTree("美".repeat(200));
    rehypeSplitWordsIntoSpans()(tree);

    const spans = paragraphSpans(tree);
    expect(spans).toHaveLength(200);
    expect(spans[0]?.style).toBe("animation-delay:0ms");
    expect(spans[66]?.style).toBe("animation-delay:1188ms");
    // 超过 67 个字后延迟封顶 1200ms，避免最后一个字等几十秒
    expect(spans[199]?.style).toBe("animation-delay:1200ms");
  });

  it("keeps English words as word-level spans (non-CJK path unchanged)", () => {
    const tree = makeParagraphTree("hello world");
    rehypeSplitWordsIntoSpans()(tree);

    const spans = paragraphSpans(tree);
    expect(spans.length).toBeGreaterThan(1);
    for (const span of spans) {
      expect(span.tagName).toBe("span");
      expect(span.className).toBe("animate-fade-in");
      // 非 CJK 路径不设置逐字延迟
      expect(span.style).toBeUndefined();
    }
  });

  it("preserves non-text children (e.g. strong) untouched", () => {
    const tree: Root = {
      type: "root",
      children: [
        {
          type: "element",
          tagName: "p",
          properties: {},
          children: [
            { type: "text", value: "看" },
            {
              type: "element",
              tagName: "strong",
              properties: {},
              children: [{ type: "text", value: "重点" }],
            },
          ],
        },
      ],
    };
    rehypeSplitWordsIntoSpans()(tree);

    const p = tree.children[0] as { children?: unknown[] };
    expect((p.children ?? []).length).toBe(2);
    expect((p.children?.[0] as { tagName?: string }).tagName).toBe("span");
    expect((p.children?.[1] as { tagName?: string }).tagName).toBe("strong");
  });
});
