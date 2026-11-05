import {randomUUID} from 'node:crypto';

export const PROVIDER = 'deepseek-account';

/** Catalog and selection stay in Harness. No account token crosses this seam. */
export async function modelState(ctx) {
  const llm = ctx.get('llm');
  if (!llm) throw new Error('DeepSeek Harness 模型服务未就绪');
  const models = await llm.listModels(PROVIDER);
  const selection = ctx.get('agentDefaultModel')?.currentSelection();
  const selected = selection?.provider === PROVIDER && models.some(m => m.id === selection.model)
    ? selection.model : models[0]?.id;
  return {provider: PROVIDER, model: selected || '', models, signedIn: models.length > 0};
}

export function safeFailure(error) {
  const code = error?.code || error?.failure?.code || 'MODEL_ERROR';
  const messages = {
    ACCOUNT_SIGN_IN_REQUIRED: '请在 DeepSeek Harness 设置中登录 DeepSeek 账户。',
    ACCOUNT_TOKEN_INVALID: 'DeepSeek 登录已失效，请在 Harness 中重新登录。',
    ACCOUNT_QUOTA_EXCEEDED: 'DeepSeek 账户额度已用完，请在 Harness 中检查账户。',
    RATE_LIMIT: 'DeepSeek 暂时限制了请求频率，请稍后继续。',
    ABORTED: '已停止回复，已收到的内容已保留。',
  };
  return {code, message: messages[code] || 'DeepSeek 请求未完成，请检查 Harness 的账户、额度和网络后继续。'};
}

/** Convert inline page images into Harness-owned immutable attachments. */
export async function normalizeMessages(ctx, messages) {
  const result = [];
  for (const message of messages) {
    const content = [];
    for (const block of message.content || []) {
      if (block.type === 'inline-image') {
        const match = /^data:(image\/[a-zA-Z0-9.+-]+);base64,([\s\S]+)$/.exec(block.url || '');
        if (!match) throw new Error('Invalid page image');
        const attachments = ctx.get('attachments');
        if (!attachments) throw new Error('Harness attachment service unavailable');
        const [attachment] = await attachments.saveImages([{data: Buffer.from(match[2], 'base64'), mediaType: match[1], name: 'paper-page.png'}]);
        content.push({type: 'image', attachment});
      } else content.push(block);
    }
    result.push({...message, id: message.id || randomUUID(), content});
  }
  return result;
}

export async function* modelStream(ctx, body, signal) {
  if (process.env.PRC_TEST_DEBUG === '1') console.log(`[paper-research-coach] dispatch ${body.tools?.length ? 'coach' : 'translation'} request`);
  const state = await modelState(ctx);
  if (!state.signedIn) {
    const error = new Error('Sign in required'); error.code = 'ACCOUNT_SIGN_IN_REQUIRED'; throw error;
  }
  const model = body.model || state.model;
  if (!state.models.some(m => m.id === model)) throw new Error('Requested model is not available on the signed-in account');
  const llm = ctx.get('llm');
  const resolved = await llm.resolveModelInfo(PROVIDER, model, signal);
  const efforts = resolved.reasoning?.efforts || [];
  const requested = efforts.some(e => e.id === body.effort) ? body.effort : undefined;
  const prepared = await llm.prepareCall({provider: PROVIDER, model, ...(requested ? {reasoningEffort: requested} : {})}, signal);
  const messages = await normalizeMessages(ctx, body.messages || []);
  yield {type: 'route', provider: PROVIDER, model};
  for await (const chunk of prepared.stream({...prepared.config, messages, system: body.system || '', tools: body.tools || [], signal})) {
    if (chunk.type === 'finish' && ['error', 'aborted'].includes(chunk.reason.kind)) {
      const failure = chunk.reason.failure;
      console.warn(`[paper-research-coach] model request: ${failure?.code || 'MODEL_ERROR'}${failure?.status ? ` (HTTP ${failure.status})` : ''}`);
      yield {...chunk, reason: {...chunk.reason, failure: {...safeFailure({code: failure?.code}), ...(failure?.status ? {status: failure.status} : {})}}};
    } else yield chunk;
  }
}
