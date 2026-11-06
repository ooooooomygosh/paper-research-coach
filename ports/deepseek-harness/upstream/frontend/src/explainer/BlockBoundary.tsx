import { Component, type ReactNode } from "react";

/**
 * One block that cannot be drawn must not take the whole page down. The model's draft is untrusted
 * input: a block can be valid for the server and still fail in the browser (a stack overflow in
 * Markdown, a layout that throws). The reader keeps every other block and the rest of the chat.
 */
export default class BlockBoundary extends Component<
  { children: ReactNode; resetKey?: unknown },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidUpdate(prev: { resetKey?: unknown }) {
    // A new draft or a replaced page gets a fresh try.
    if (this.state.failed && prev.resetKey !== this.props.resetKey) this.setState({ failed: false });
  }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <p className="xp-broken" role="alert">
        这一块画不出来。其他内容不受影响；可以让教练换一种写法重讲这一块。
      </p>
    );
  }
}
