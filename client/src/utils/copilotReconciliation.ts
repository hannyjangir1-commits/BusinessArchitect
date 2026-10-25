import { CopilotMessage, CopilotSendResult } from '../types';

/**
 * Authoritative message reconciliation ensuring exactly one identity per persisted message.
 * - Replaces temporary client identity with the authoritative database user_message.
 * - Appends assistant_message if present.
 * - Deduplicates overlapping message IDs without deduplicating by text.
 * - Produces a stable chronological sort by created_at and id.
 */
export function reconcileSend(
  previous: CopilotMessage[],
  tempId: string,
  result: CopilotSendResult
): CopilotMessage[] {
  const userMsgId = result.user_message?.id;
  const assistantMsgId = result.assistant_message?.id;

  const filtered = previous.filter(m =>
    m.id !== tempId &&
    m.client_msg_id !== tempId &&
    (!userMsgId || m.id !== userMsgId) &&
    (!assistantMsgId || m.id !== assistantMsgId)
  );

  const savedUserMsg: CopilotMessage = {
    ...result.user_message,
    status: 'saved'
  };
  filtered.push(savedUserMsg);

  if (result.assistant_message) {
    filtered.push({
      ...result.assistant_message,
      status: 'saved'
    });
  }

  return filtered.sort((a, b) => {
    const timeA = new Date(a.created_at).getTime();
    const timeB = new Date(b.created_at).getTime();
    if (timeA !== timeB) return timeA - timeB;
    return a.id.localeCompare(b.id);
  });
}
