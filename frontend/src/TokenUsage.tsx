import type { PipelineUsage, TokenUsage } from "./types";
import s from "./Studio.module.css";

const stages = [
  ["script", "Tạo kịch bản"],
  ["graphics", "Preview phong cách đồ họa"],
  ["animation", "Preview HTML animation"],
] as const;
const number = (value: number) => value.toLocaleString("vi-VN");

function count(usage: TokenUsage | undefined, field: "input_tokens" | "output_tokens" | "total_tokens") {
  if (!usage) return "—";
  if (usage.unknown_requests && usage.requests === usage.unknown_requests) return "Chưa có dữ liệu";
  return `${usage.unknown_requests ? "≥ " : ""}${number(usage[field])}`;
}

export function StageUsage({ label, usage }: { label: string; usage?: TokenUsage }) {
  return <div className={s.stageUsage} aria-label={`Token ${label}`}>
    <strong>Token · {label}</strong>
    <div><span>Input <b>{count(usage, "input_tokens")}</b></span>
      <span>Output <b>{count(usage, "output_tokens")}</b></span>
      <span>Tổng <b>{count(usage, "total_tokens")}</b></span></div>
    {!usage ? <small>Chưa có dữ liệu token cho giai đoạn này.</small> :
      <small>{number(usage.requests)} lần gọi AI
        {usage.cached_input_tokens > 0 && ` · ${number(usage.cached_input_tokens)} input token từ cache`}
        {usage.unknown_requests > 0 && ` · ${usage.unknown_requests} lần chưa có số liệu`}</small>}
  </div>;
}

export function TokenSummary({ usage }: { usage?: PipelineUsage }) {
  const rows = stages.flatMap(([key]) => usage?.[key] ? [usage[key]!] : []);
  const total = rows.length ? rows.reduce((sum, row) => ({
    input_tokens: sum.input_tokens + row.input_tokens,
    output_tokens: sum.output_tokens + row.output_tokens,
    cached_input_tokens: sum.cached_input_tokens + row.cached_input_tokens,
    total_tokens: sum.total_tokens + row.total_tokens,
    requests: sum.requests + row.requests,
    unknown_requests: sum.unknown_requests + row.unknown_requests,
  }), { input_tokens: 0, output_tokens: 0, cached_input_tokens: 0,
    total_tokens: 0, requests: 0, unknown_requests: 0 }) : undefined;
  const incomplete = rows.length < 3 || !!total?.unknown_requests;
  return <div className={s.tokenSummary}>
    <h3>Thống kê token AI</h3>
    <div className={s.tokenTableScroll}><table>
      <thead><tr><th scope="col">Giai đoạn</th><th scope="col">Input</th><th scope="col">Output</th><th scope="col">Tổng token</th></tr></thead>
      <tbody>{stages.map(([key, label]) => <tr key={key}>
        <th scope="row">{label}</th><td>{count(usage?.[key], "input_tokens")}</td>
        <td>{count(usage?.[key], "output_tokens")}</td><td>{count(usage?.[key], "total_tokens")}</td>
      </tr>)}</tbody>
      <tfoot><tr><th scope="row">{incomplete ? "Tổng đã ghi nhận" : "Tổng 3 giai đoạn"}</th>
        <td>{count(total, "input_tokens")}</td><td>{count(total, "output_tokens")}</td><td>{count(total, "total_tokens")}</td>
      </tr></tfoot>
    </table></div>
    <p>Số liệu Codex CLI báo cho lượt tạo hiện tại, gồm các lần gọi lại trong cùng tác vụ. Token cache đã nằm trong input.
      {incomplete && " Tổng sẽ đầy đủ khi cả 3 giai đoạn có số liệu. Dấu ≥ chỉ phần token đã ghi nhận khi có lần gọi thiếu dữ liệu."}</p>
  </div>;
}
