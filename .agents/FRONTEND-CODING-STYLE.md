# Frontend Coding Style

Use the [Google TypeScript Style Guide](https://google.github.io/styleguide/tsguide.html) as a reference for TypeScript. Follow Lens conventions and the project's [Biome configuration](../frontend/biome.json) and [TypeScript configuration](../frontend/tsconfig.json). See [DESIGN.md](DESIGN.md) for visual and component styling rules.

## TypeScript and JSX

- Use `PascalCase.tsx` for component files and `useXxx.ts` for hook files. Name handlers `handleXxx` and callback props `onXxx`.
- Use [`unknown` for values of unknown type](https://google.github.io/styleguide/tsguide.html#using-unknown-over-any). Narrow them with runtime checks. Type assertions (`as`) and non-null assertions (`!`) do not perform runtime validation.
- Follow the [HTML semantics section of Google's HTML/CSS Style Guide](https://google.github.io/styleguide/htmlcssguide.html#semantics) in JSX. Use buttons for actions and links for navigation.

## Lens conventions

- Send Lens API requests through [`apiRequest` or `apiFetch`](../frontend/src/lib/api/client.ts) to share authentication and error handling.
- Reuse TanStack Query hooks and cache keys for server data. After a successful mutation, update or invalidate the affected queries. Keep editable form drafts in local state and derive display values from props or state.
- Provide both `zh-CN` and `en-US` for interface text through the existing [`useI18n` and `titleForLocale`](../frontend/src/lib/I18nContext.tsx) patterns.
