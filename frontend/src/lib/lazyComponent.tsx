import { type ComponentType, lazy, Suspense } from "react";

/**
 * Loads a component on demand, rendering nothing until its chunk arrives.
 *
 * Keeps the Suspense boundary next to the component so a pending chunk cannot
 * blank out the surrounding screen.
 */
export function lazyComponent<P extends object>(
  load: () => Promise<ComponentType<P>>,
) {
  const Loaded = lazy(() =>
    load().then((Component) => ({ default: Component })),
  );

  return function LazyComponent(props: P) {
    return (
      <Suspense fallback={null}>
        <Loaded {...props} />
      </Suspense>
    );
  };
}
