import { Info } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';
import { useThreads } from '@/entities/thread';
import { CheckpointTimeline, ThreadStateSummary } from '@/widgets/checkpoint-timeline';

export default function InspectorPage() {
  const { threadId } = useParams();
  const navigate = useNavigate();
  const { data: threads } = useThreads();

  return (
    <div className="flex flex-col gap-4 p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">State inspector</h1>
        <p className="text-muted-foreground">Read-only view of a conversation's checkpoints.</p>
      </div>
      <p className="bg-muted flex items-start gap-2 rounded-md p-3 text-sm">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        Every step of a run is saved as a checkpoint, so after a crash or restart the agent resumes
        from the last one instead of starting over.
      </p>
      <label className="flex flex-col gap-1 text-sm font-medium sm:max-w-sm">
        Conversation
        <select
          className="border-input bg-background h-9 rounded-md border px-2 text-sm font-normal"
          value={threadId ?? ''}
          onChange={(e) => {
            void navigate(`/app/inspector/${e.target.value}`);
          }}
        >
          <option value="" disabled>
            Select a conversation…
          </option>
          {threads?.map((thread) => (
            <option key={thread.id} value={thread.id}>
              {thread.title || 'New conversation'}
            </option>
          ))}
        </select>
      </label>
      {threadId && (
        <>
          <ThreadStateSummary threadId={threadId} />
          <CheckpointTimeline key={threadId} threadId={threadId} />
        </>
      )}
    </div>
  );
}
