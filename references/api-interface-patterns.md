# API Interface Patterns

Illustrative examples only. The mandatory API-design rules live in
[`tgd-define-api`](../skills/tgd-define-api/SKILL.md); examples here never
override that skill or project-specific contracts.

## Contract and Error Shapes

```typescript
interface TaskAPI {
  createTask(input: CreateTaskInput): Promise<Task>;
  listTasks(params: ListTasksParams): Promise<PaginatedResult<Task>>;
  getTask(id: TaskId): Promise<Task>;
  updateTask(id: TaskId, input: UpdateTaskInput): Promise<Task>;
  deleteTask(id: TaskId): Promise<void>;
}

interface APIError {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}
```

This example mirrors the main skill's REST status mapping: `400` invalid
request, `401` unauthenticated, `403` unauthorized, `404` absent resource,
`409` conflict, `422` semantic validation failure, and `500` safe server error.

## Boundary Validation

```typescript
app.post('/api/tasks', async (req, res) => {
  const result = CreateTaskSchema.safeParse(req.body);
  if (!result.success) {
    return res.status(422).json({
      error: {
        code: 'VALIDATION_ERROR',
        message: 'Invalid task data',
        details: result.error.flatten(),
      },
    });
  }

  const task = await taskService.create(result.data);
  return res.status(201).json(task);
});
```

## Additive Evolution

```typescript
interface CreateTaskInput {
  title: string;
  description?: string;
  priority?: 'low' | 'medium' | 'high';
  labels?: string[];
}
```

Removing `description` or changing `priority` from the established string enum
to a number would instead require a governed migration.

## REST Resource Example

```text
GET    /api/tasks
POST   /api/tasks
GET    /api/tasks/:id
PATCH  /api/tasks/:id
DELETE /api/tasks/:id
GET    /api/tasks/:id/comments
POST   /api/tasks/:id/comments
```

Example list request and response:

```http
GET /api/tasks?page=1&pageSize=20&sortBy=createdAt&sortOrder=desc
```

```json
{
  "data": [],
  "pagination": {
    "page": 1,
    "pageSize": 20,
    "totalItems": 142,
    "totalPages": 8
  }
}
```

Filters can remain query parameters:

```http
GET /api/tasks?status=in_progress&assignee=user123&createdAfter=2025-01-01
```

A partial update changes only supplied fields:

```http
PATCH /api/tasks/123
Content-Type: application/json

{ "title": "Updated title" }
```

## TypeScript Variant Examples

```typescript
type TaskStatus =
  | { type: 'pending' }
  | { type: 'in_progress'; assignee: string; startedAt: Date }
  | { type: 'completed'; completedAt: Date; completedBy: string }
  | { type: 'cancelled'; reason: string; cancelledAt: Date };

function getStatusLabel(status: TaskStatus): string {
  switch (status.type) {
    case 'pending': return 'Pending';
    case 'in_progress': return `In progress (${status.assignee})`;
    case 'completed': return `Done on ${status.completedAt}`;
    case 'cancelled': return `Cancelled: ${status.reason}`;
  }
}
```

```typescript
interface CreateTaskInput {
  title: string;
  description?: string;
}

interface Task {
  id: TaskId;
  title: string;
  description: string | null;
  createdAt: Date;
  updatedAt: Date;
  createdBy: UserId;
}

type TaskId = string & { readonly __brand: 'TaskId' };
type UserId = string & { readonly __brand: 'UserId' };
```
