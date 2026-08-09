# Release and Migration Patterns

These are optional, illustrative examples only. They do not define rollout thresholds, migration sequencing, safety gates, failure behavior, or verification. Those requirements remain in the parent `tgd-release-ship` or `tgd-release-migration` skill.

## Feature Flag Check

```typescript
const flags = await getFeatureFlags(userId);

if (flags.taskSharing) {
  return <TaskSharingPanel task={task} />;
}

return null;
```

## Rollout Shape

```text
DEPLOY with flag OFF
  → ENABLE for team or beta
  → CANARY at 5%
  → INCREASE to 25%, 50%, 100%
  → MONITOR at every stage
  → REMOVE the flag and dead path
```

## Monitoring Inventory

```text
Application
├── Error rate by endpoint
├── p50, p95, p99 response time
├── Request volume and active users
└── Business metrics

Infrastructure
├── CPU and memory
├── Database connections and disk
├── Network latency
└── Queue depth

Client
├── LCP, INP, CLS
├── JavaScript errors
├── Client-visible API errors
└── Page-load time
```

## Error Reporting Sketch

This example returns a generic user message while sending diagnostic context to the reporter.

```typescript
class ErrorBoundary extends React.Component {
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    reportError(error, {
      componentStack: info.componentStack,
      userId: getCurrentUser()?.id,
      page: window.location.pathname,
    });
  }

  render() {
    if (this.state.hasError) {
      return <ErrorFallback onRetry={() => this.setState({ hasError: false })} />;
    }
    return this.props.children;
  }
}

app.use((err: Error, req: Request, res: Response, next: NextFunction) => {
  reportError(err, {
    method: req.method,
    url: req.url,
    userId: req.user?.id,
  });

  res.status(500).json({
    error: { code: 'INTERNAL_ERROR', message: 'Something went wrong' },
  });
});
```

## Rollback Plan Template

```markdown
## Rollback Plan for [Feature/Release]

### Trigger Conditions
- Error rate > 2x baseline
- P95 latency > [X]ms
- User reports of [specific issue]

### Rollback Steps
1. Disable feature flag (if applicable), or deploy/revert to [known version].
2. Verify health check and error monitoring.
3. Notify [team/channel] of the rollback.

### Database Considerations
- Migration [X] rollback: [command or procedure]
- Data inserted by the new feature: [preserved / cleaned up]

### Expected Time
- Feature flag: < 1 minute
- Previous version deploy: < 5 minutes
- Database rollback: < 15 minutes
```

## Deprecation Notice Template

```markdown
## Deprecation Notice: OldService

**Status:** Deprecated as of 2025-03-01
**Replacement:** NewService
**Removal date:** Advisory — no hard deadline yet
**Reason:** OldService requires manual scaling and lacks observability.

### Migration Guide
1. Replace the old import with the new service import.
2. Update configuration using the project-specific mapping.
3. Run the migration verification script: `npx migrate-check`.
```

## Migration Pattern Sketches

### Strangler

```text
Phase 1: new 0%, old 100%
Phase 2: new 10%, old 90%
Phase 3: new 50%, old 50%
Phase 4: new 100%, old idle
Phase 5: remove old
```

### Adapter

```typescript
class LegacyTaskService implements OldTaskAPI {
  constructor(private newService: NewTaskService) {}

  getTask(id: number): OldTask {
    const task = this.newService.findById(String(id));
    return this.toOldFormat(task);
  }
}
```

### Per-Consumer Feature Flag

```typescript
function getTaskService(userId: string): TaskService {
  if (featureFlags.isEnabled('new-task-service', { userId })) {
    return new NewTaskService();
  }
  return new LegacyTaskService();
}
```
