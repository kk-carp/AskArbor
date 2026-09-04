import type { DocumentStatus, MeResponse, SpaceId, TicketStatus, UserRole } from "@/types";

export function roleLabel(role: UserRole): string {
  const map: Record<UserRole, string> = {
    student: "学员",
    employee: "内部员工",
    teaching: "教学岗",
  };
  return map[role];
}

/** 教学岗在用户表里 role 仍可能是 employee，展示以 is_teaching 为准 */
export function displayRole(user: MeResponse): string {
  if (user.is_teaching) {
    return "教学岗";
  }
  return roleLabel(user.role);
}

export function spaceLabel(space: SpaceId): string {
  return space === "student" ? "课程空间" : "内部空间";
}

export function documentStatusLabel(status: DocumentStatus): string {
  const map: Record<DocumentStatus, string> = {
    processing: "处理中",
    ready: "可检索",
    failed: "失败",
    offline: "已下线",
  };
  return map[status];
}

export function ticketStatusLabel(status: TicketStatus): string {
  return status === "open" ? "待回复" : "已回复";
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  const pad = (num: number) => String(num).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function shortId(value: string): string {
  return value.length <= 8 ? value : `${value.slice(0, 8)}…`;
}
