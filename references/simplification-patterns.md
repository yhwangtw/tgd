# Simplification Patterns

Illustrative examples for `tgd-review-simplify`. They are recipes, not policy; preserve behavior and follow the owning skill.

## Signal-to-Response Examples

| Signal | Possible response |
|---|---|
| Nesting of 3+ levels | Guard clauses or a named helper |
| 50+ line multi-purpose function | Split by responsibility |
| Nested ternary | `if`/`else`, `switch`, or lookup |
| Positional booleans | Options object or separate functions |
| Repeated conditional | Named predicate |
| Generic or misleading name | Name the content or side effect |
| What-comment | Remove it; keep why-comments |
| Duplicated logic | Shared function after confirming sameness |
| Value-free wrapper | Call the underlying function directly |
| Speculative pattern | Prefer the current direct use case |

## TypeScript and JavaScript

```typescript
// Readable status mapping instead of a nested ternary
function getStatusLabel(item: Item): string {
  if (item.isNew) return 'New';
  if (item.isUpdated) return 'Updated';
  if (item.isArchived) return 'Archived';
  return 'Active';
}

// Filtering rather than manual accumulation
const activeUsers = users.filter((user) => user.isActive);

// Direct boolean expression
function isValid(input: string): boolean {
  return input.length > 0 && input.length < 100;
}
```

Compact syntax is not inherently simpler. For example, prefer a named loop or intermediate `Map` over a spread-heavy reducer when the reducer makes state updates difficult to parse.

## Python

```python
# Dictionary comprehension for a direct mapping
result = {item.id: item.name for item in items}

# Guard clauses for nested validation
def process(data):
    if data is None:
        raise TypeError("Data is None")
    if not data.is_valid():
        raise ValueError("Invalid data")
    if not data.has_permission():
        raise PermissionError("No permission")
    return do_work(data)
```

## React and JSX

```tsx
function UserBadge({ user }: Props) {
  const variant = user.isAdmin ? 'admin' : 'default';
  const label = user.isAdmin ? 'Admin' : 'User';
  return <Badge variant={variant}>{label}</Badge>;
}
```

Prop drilling may suggest context or composition, but that is a judgment call: flag it for review rather than auto-refactoring it.

## Before/After Review Prompt

```text
- Is the result genuinely easier to understand?
- Does it introduce a pattern foreign to the codebase?
- Is every input, output, error, side effect, and ordering unchanged?
- Does the untouched test suite still pass?
- Is the diff smaller in conceptual load, not merely line count?
```
