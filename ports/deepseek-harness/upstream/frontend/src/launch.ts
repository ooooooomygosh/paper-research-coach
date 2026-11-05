export function readLaunchInput(value: string, origin: string) {
  const input = value.trim();
  if (!input) throw new Error("请粘贴启动器提供的完整链接。");
  if (!/^https?:\/\//i.test(input))
    return { token: input, paper: "", conversation: "" };
  let url: URL;
  try {
    url = new URL(input);
  } catch {
    throw new Error("启动链接格式不正确，请重新复制。");
  }
  if (url.origin !== origin)
    throw new Error("这个链接属于另一处工作台，请使用当前工作台的启动链接。");
  const params = new URLSearchParams(url.hash.slice(1));
  const token = params.get("token") || "";
  if (!token) throw new Error("这个地址没有登录信息，请从本机启动器打开。");
  return {
    token,
    paper: params.get("paper") || "",
    conversation: params.get("conversation") || "",
  };
}
