import { ArrowRight, Plus } from "lucide-react";
import "./onboarding.css";

export default function Welcome({ onImport, onConnect }: {
  onImport: () => void;
  onConnect: () => void;
}) {
  return (
    <section className="welcome welcome-reading" aria-labelledby="welcome-title">
      <span className="eyebrow">从一篇值得读的论文开始</span>
      <h1 id="welcome-title">不止读懂。<br />形成自己的判断。</h1>
      <p className="welcome-lead">原文放在眼前，问题留在身边。<br />从一个看不懂、想核实，或不同意的地方开始。</p>
      <div className="welcome-actions">
        <button className="primary" onClick={onImport}><Plus size={17} />导入论文</button>
        <button className="text-button" onClick={onConnect}>连接 Zotero <ArrowRight size={16} /></button>
      </div>
      <ol className="first-reading" aria-label="第一轮阅读">
        <li><span>01</span><div><strong>看一处原文</strong><p>一句主张、一条公式，或一张图。无需按顺序读完。</p></div></li>
        <li><span>02</span><div><strong>解决一个疑问</strong><p>选中原文再讨论。需要提示或直接解释，由你决定。</p></div></li>
        <li><span>03</span><div><strong>留下自己的判断</strong><p>记下相信什么、证据在哪、还有什么没被证明。</p></div></li>
      </ol>
      <p className="welcome-footnote">先读原文，不必先配齐工具。AI 带读需要本机 Codex CLI；Zotero 与整篇翻译均为可选。</p>
      <details className="welcome-demo">
        <summary>还没有准备好论文？先体验示例</summary>
        <p>安装后在终端运行 <code>prc-demo</code>。示例使用合成论文和独立临时书库，不读取你的文献；退出服务后清理示例记录。</p>
      </details>
    </section>
  );
}
