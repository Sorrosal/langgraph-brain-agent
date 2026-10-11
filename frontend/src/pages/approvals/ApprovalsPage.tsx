import { ApprovalQueue } from '@/widgets/approval-queue';

export default function ApprovalsPage() {
  return (
    <div className="flex max-w-3xl flex-col gap-4 p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Approvals</h1>
        <p className="text-muted-foreground">
          Conversations paused on a decision. Open one to review it.
        </p>
      </div>
      <ApprovalQueue />
    </div>
  );
}
