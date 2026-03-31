import { lazy, ComponentType, LazyExoticComponent } from 'react'

export function lazyWithPreload<T extends ComponentType<Record<string, never>>>(
  factory: () => Promise<{ default: T }>
): LazyExoticComponent<T> & { preload: () => Promise<{ default: T }> } {
  const LazyComponent = lazy(factory)
  return Object.assign(LazyComponent, {
    preload: factory,
  })
}
