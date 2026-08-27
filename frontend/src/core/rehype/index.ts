import type { Element, Root, ElementContent } from "hast";
import { useMemo } from "react";
import { visit } from "unist-util-visit";
import type { BuildVisitor } from "unist-util-visit";

const CJK_TEXT_RE =
  /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}]/u;

// 中文/日文/韩文逐字"打字机"效果：每个字符递增延迟淡入。
// 延迟有上限，避免长消息最后一个字要等几十秒才出现。
const CJK_STEP_MS = 18;
const CJK_MAX_DELAY_MS = 1200;

export function rehypeSplitWordsIntoSpans() {
  return (tree: Root) => {
    visit(tree, "element", ((node: Element) => {
      if (
        ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "strong"].includes(
          node.tagName,
        ) &&
        node.children
      ) {
        const newChildren: Array<ElementContent> = [];
        node.children.forEach((child) => {
          if (child.type === "text") {
            if (CJK_TEXT_RE.test(child.value)) {
              // 逐字拆分：位置决定延迟（位置稳定，React 复用 DOM 节点不会重启动画）
              const offset = newChildren.length;
              Array.from(child.value).forEach((char, i) => {
                newChildren.push({
                  type: "element",
                  tagName: "span",
                  properties: {
                    className: "animate-fade-in",
                    style: `animation-delay:${Math.min(
                      (offset + i) * CJK_STEP_MS,
                      CJK_MAX_DELAY_MS,
                    )}ms`,
                  },
                  children: [{ type: "text", value: char }],
                });
              });
              return;
            }
            const segmenter = new Intl.Segmenter("zh", { granularity: "word" });
            const segments = segmenter.segment(child.value);
            const words = Array.from(segments)
              .map((segment) => segment.segment)
              .filter(Boolean);
            words.forEach((word: string) => {
              newChildren.push({
                type: "element",
                tagName: "span",
                properties: {
                  className: "animate-fade-in",
                },
                children: [{ type: "text", value: word }],
              });
            });
          } else {
            newChildren.push(child);
          }
        });
        node.children = newChildren;
      }
    }) as BuildVisitor<Root, "element">);
  };
}

export function useRehypeSplitWordsIntoSpans(enabled = true) {
  const rehypePlugins = useMemo(
    () => (enabled ? [rehypeSplitWordsIntoSpans] : []),
    [enabled],
  );
  return rehypePlugins;
}
