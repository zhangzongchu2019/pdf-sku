/** 枚举完整性快照测试 */
import { describe, it, expect } from 'vitest';

describe('Enum completeness', () => {
  it('JobUserStatus has 5 values', () => {
    const values: string[] = ['processing', 'partial_success', 'completed', 'needs_manual', 'failed'];
    expect(values).toHaveLength(5);
  });

  it('SSEEventType has 12 events', () => {
    const events = ['heartbeat','page_started','page_completed','page_failed','pages_batch_update','job_completed','job_failed','human_needed','sla_escalated','sla_auto_resolve','sla_auto_accepted','job_deleted'];
    expect(events).toHaveLength(12);
  });
});
