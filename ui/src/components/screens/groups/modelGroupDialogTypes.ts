import type { Dispatch, FormEventHandler, SetStateAction } from "react";
import type {
  ModelGroup,
  ModelGroupCandidateItem,
  ProtocolKind,
} from "@/lib/api";
import type {
  CandidateChannelGroup,
  CandidateSearchMode,
  FoldedMember,
  FormState,
} from "./modelGroupUtils";

export interface GroupEditorDialogProps {
  dialogOpen: boolean;
  setDialogOpen: Dispatch<SetStateAction<boolean>>;
  editingId: string | null;
  locale: "zh-CN" | "en-US";
  submit: FormEventHandler<HTMLFormElement>;
  form: FormState;
  setForm: Dispatch<SetStateAction<FormState>>;
  toggleProtocol: (protocol: ProtocolKind) => void;
  routeTargetOptions: ModelGroup[];
  changeRouteTarget: (routeGroupId: string) => void;
  candidateSearchMode: CandidateSearchMode;
  changeCandidateSearchMode: (mode: CandidateSearchMode) => void;
  candidateSearch: string;
  changeCandidateSearch: (value: string) => void;
  addMatchedItems: () => void;
  candidateRegexInvalid: boolean;
  filteredCandidates: ModelGroupCandidateItem[];
  refetchCandidates: () => unknown;
  isFetchingCandidates: boolean;
  applySavedFilter: () => void;
  clearSavedFilter: () => void;
  groupedCandidates: CandidateChannelGroup[];
  expandedChannels: string[];
  toggleChannel: (channelId: string) => void;
  foldedMembers: FoldedMember[];
  addCandidate: (candidate: ModelGroupCandidateItem) => void;
  sitesIsError: boolean;
  candidateIsError: boolean;
  candidateListError: unknown;
  invalidSelectedMemberCount: number;
  removeInvalidItems: () => void;
  setAllMembersEnabled: (enabled: boolean) => void;
  showEnabledOnly: boolean;
  setShowEnabledOnly: Dispatch<SetStateAction<boolean>>;
  visibleFoldedMembers: Array<{ member: FoldedMember; index: number }>;
  draggingIndex: number | null;
  toggleFoldedMember: (foldKey: string, enabled: boolean) => void;
  removeFoldedMember: (foldKey: string) => void;
  setDraggingIndex: Dispatch<SetStateAction<number | null>>;
  moveFoldedMember: (fromIndex: number, toIndex: number) => void;
}

export interface DeleteGroupDialogProps {
  deleteTarget: ModelGroup | null;
  locale: "zh-CN" | "en-US";
  busyId: string | null;
  setDeleteTarget: Dispatch<SetStateAction<ModelGroup | null>>;
  remove: (item: ModelGroup) => void;
}
