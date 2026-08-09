# UI Engineering Patterns

Illustrative examples only. The mandatory UI rules and source precedence live
in [`tgd-develop-ui`](../skills/tgd-develop-ui/SKILL.md); project components and
the approved design system take precedence over every example here.

## Colocated Component Shape

```text
src/components/
  TaskList/
    TaskList.tsx
    TaskList.test.tsx
    TaskList.stories.tsx
    use-task-list.ts
    types.ts
```

## Composition and Presentation

```tsx
<Card>
  <CardHeader><CardTitle>Tasks</CardTitle></CardHeader>
  <CardBody><TaskList tasks={tasks} /></CardBody>
</Card>
```

```tsx
export function TaskListContainer() {
  const { tasks, isLoading, error, refetch } = useTasks();
  if (isLoading) return <TaskListSkeleton />;
  if (error) return <ErrorState message="Failed to load tasks" retry={refetch} />;
  if (tasks.length === 0) return <EmptyState message="No tasks yet" />;
  return <TaskList tasks={tasks} />;
}

export function TaskList({ tasks }: { tasks: Task[] }) {
  return (
    <ul role="list" className="divide-y">
      {tasks.map(task => <TaskItem key={task.id} task={task} />)}
    </ul>
  );
}
```

## Token Examples

```css
/* Illustrative values; the real project supplies its spacing tokens. */
.task-list {
  padding: 1rem;
  gap: 0.75rem;
}
```

Names such as `text-primary`, `bg-surface`, and `border-default` illustrate
semantic intent rather than prescribing a token vocabulary.

## Native Interaction and Labels

```tsx
<button type="button" onClick={handleClick}>Click me</button>

<button type="button" aria-label="Close dialog">
  <XIcon aria-hidden="true" />
</button>

<label htmlFor="email">Email</label>
<input id="email" type="email" />
```

## Focus Movement Example

```tsx
function Dialog({ isOpen, onClose }: DialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (isOpen && !dialog.open) dialog.showModal();
    if (!isOpen && dialog.open) dialog.close();
  }, [isOpen]);

  return (
    <dialog ref={dialogRef} aria-labelledby="task-dialog-title" onClose={onClose}>
      <h2 id="task-dialog-title">Tasks</h2>
      <button autoFocus type="button" onClick={() => dialogRef.current?.close()}>
        Close
      </button>
    </dialog>
  );
}
```

This native-dialog example illustrates modal focus containment and movement;
an established project dialog primitive may provide the same behavior.

## Empty and Loading States

```tsx
function EmptyTasks({ onCreateTask }: { onCreateTask(): void }) {
  return (
    <div role="status" className="text-center py-12">
      <TasksEmptyIcon aria-hidden="true" className="mx-auto h-12 w-12 text-muted" />
      <h2 className="mt-2 text-sm font-medium">No tasks</h2>
      <p className="mt-1 text-sm text-muted">Create a task to get started.</p>
      <Button className="mt-4" onClick={onCreateTask}>Create task</Button>
    </div>
  );
}

function TaskListSkeleton() {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Loading tasks">
      {Array.from({ length: 3 }).map((_, index) => (
        <div key={index} className="h-12 bg-muted animate-pulse rounded" />
      ))}
    </div>
  );
}
```

## Responsive Shape

```tsx
<div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
  {items.map(item => <ItemCard key={item.id} item={item} />)}
</div>
```

## Optimistic Update with Rollback

```tsx
function useToggleTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: toggleTask,
    onMutate: async (taskId) => {
      await queryClient.cancelQueries({ queryKey: ['tasks'] });
      const previous = queryClient.getQueryData<Task[]>(['tasks']);
      queryClient.setQueryData<Task[]>(['tasks'], old =>
        old?.map(task => task.id === taskId ? { ...task, done: !task.done } : task)
      );
      return { previous };
    },
    onError: (_error, _taskId, context) => {
      queryClient.setQueryData(['tasks'], context?.previous);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['tasks'] }),
  });
}
```
