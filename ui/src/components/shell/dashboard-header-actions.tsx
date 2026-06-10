"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from "react";

type DashboardHeaderActionsContextValue = {
  setActions: Dispatch<SetStateAction<ReactNode>>;
};

export const DashboardHeaderActionsContext =
  createContext<DashboardHeaderActionsContextValue | null>(null);

export function useDashboardHeaderActionsState() {
  const [actions, setActions] = useState<ReactNode>(null);
  const value = useMemo(() => ({ setActions }), [setActions]);

  return { actions, value };
}

export function DashboardHeaderActions({
  children,
}: {
  children: ReactNode;
}) {
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
