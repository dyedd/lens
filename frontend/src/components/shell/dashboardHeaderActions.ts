import {
  createContext,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

type DashboardHeaderActionsContextValue = {
  setActions: Dispatch<SetStateAction<ReactNode>>;
};

export const DashboardHeaderActionsContext =
  createContext<DashboardHeaderActionsContextValue | null>(null);

/** Creates the shared state used to populate dashboard header actions. */
export function useDashboardHeaderActionsState() {
  const [actions, setActions] = useState<ReactNode>(null);
  const value = useMemo(() => ({ setActions }), []);

  return { actions, value };
}

/** Publishes page-specific actions to the dashboard header. */
export function DashboardHeaderActions({ children }: { children: ReactNode }) {
  const context = useContext(DashboardHeaderActionsContext);

  useEffect(() => {
    if (!context) {
      return;
    }

    context.setActions(children);
  }, [children, context]);

  useEffect(() => {
    if (!context) {
      return;
    }

    return () => context.setActions(null);
  }, [context]);

  return null;
}
