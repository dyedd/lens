# Backend Coding Style

This document describes the coding style for human contributors and AI agents.

Rules below distinguish Python behavior from preferences specific to this coding style.

## Principles

Above all, be thorough in producing high-quality, correct code that completely fulfills the user's task. Keep the code easy to read.

Write clean, professional, maintainable code. Match the surrounding codebase's conventions where they exist; where they don't, follow these rules. For Python topics these rules do not cover, follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html); where the two disagree, these rules win. Do not load the entire Google guide by default. Consult the relevant sections as needed, and read it in full only for a comprehensive style audit.

Solve the task completely with the smallest change, and leave unrelated files unchanged. Code you do not modify can stay as it is even when it does not follow these rules. Before consolidating or removing code, preserve the behavior its callers rely on unless the task requires changing it.

After correctness, the overriding goal is simplicity: fewer, smaller files and fewer functions. Avoid speculative generality.

Make sure that code is human readable. Do not use fewer lines, shorter variable names, minified formatting, or dense one-liners as substitutes for simplicity. Ensure that comments and variable names are readable and understandable to a human. Code-golfed expressions count as overly complex when they encode many branches, conditions, or hidden assumptions.

Naming clarity is part of that bar, not a polish pass. A reader should understand what a name represents without opening the function body. Include units for quantities when they are not clear from the name or surrounding interface. Expand abbreviations when they hide meaning, and use established domain terms consistently. The NAMING section below is the rule.

Imports are part of that bar too. Prefer module-scope imports so a reader can see a module's dependencies. Python also permits function-local imports, which defer loading and can sometimes resolve an import cycle; use them only when there is a concrete reason. The IMPORTS section below is the rule.

## SIMPLICITY & NON-DUPLICATION

- Reuse existing logic in the user's repo when you can. You should reuse existing classes, methods, representations, and APIs in the codebase as long as they preserve correctness.
- Avoid unnecessary indirection and abstraction. Helper functions, utility functions, and class abstractions can add cognitive complexity even when they do not add branches.
- Introduce a helper, wrapper, or abstraction layer only when it is used at least twice (≥2 call sites) now and genuinely clarifies the call site.
- Don't reinvent what stdlib or an already-imported dep provides (`itertools`, `functools`, `collections`, `pathlib`, `dataclasses`, `pydantic`, `torch.nn.functional`). A 3-line wrapper around `lru_cache` is noise.
- Don't pre-extract `_helper`/`_impl` for "cleaner main flow" unless it's reused at least twice (≥2 call sites) or too long to read in one screen. A 60-line top-to-bottom function beats three 20-line `_step_one/_two/_three` called once each.
- Don't add interfaces/base classes/registries/plugin systems before a second concrete implementation exists. Two cases first, then abstract.
- Reuse alone is not enough to justify a trivial helper: inline a short operation used only once (1 call site) when extraction adds indirection without clarity. Keep nested callbacks local when their scope or captured state requires it.
- Remove redundant intermediate variables, assignments, and parameter passing.

  Wrong:

  ```python
  sum = a + b
  result = sum
  return result
  ```

  Right:

  ```python
  return a + b
  ```

## LANGUAGE, COMMENTS, COMMITS & PRS

- English only: comments, docstrings, log strings, CLI help. (User-facing translatable strings go through i18n — not this rule's concern.) If the repo is non-English, match it.
- A prose paragraph is one line. Break the line only when the paragraph ends, including in Markdown documentation. Do not wrap in the middle of a sentence.
- Comments sparse, one-line, only for the genuinely non-obvious. Restating code is noise.
- Comments must be self-contained and explain _why_, not _how_ or _what_. Don't narrate what a code block does or how it does it — the code already shows that. But only document the "why" when specific codes are hard to understand without the context of the comments. Avoid verbose "why" rationale in comments.
- Comments and documents describe the current code for a reader who has seen only the current files.
- Diff-log test: a comment that only makes sense to someone who knows the previous version or the conversation that produced it is a diff log. Words such as "still", "now", "no longer", "instead of", "originally", "previously", "historical", and "fix" usually mark one. Rewrite it as a plain statement about the current code, or delete it.

  Wrong:

  ```python
  # Keep a and b as historical code. Fix it by adding c=3.
  f(a, b, c=3)
  ```

  Right:

  ```python
  # Set c=3 because case X needs Y.
  f(a, b, c=3)
  ```

- Commit messages and PR descriptions describe the change and its reason. Leave out the process that led to it, such as rejected attempts, review rounds, and conversation details.
- Never include private conversation details, prompts, or iteration history unrelated to the project.
- Wrong - the strictly forbidden "东坡肉" residue pattern (below, "我" is the user and "它" is the agent):

  > 我让它做一盘番茄炒蛋，它往里还加了东坡肉。
  > 我说有必要加东坡肉吗？它说你说得对，然后把东坡肉去掉。
  > 我说好，你提 PR 吧。再一看，它 PR 写着「番茄炒蛋（无东坡肉）」并且注释里会写一大堆为什么本道菜不需要加东坡肉。

  The output must not contain any trace of "东坡肉". If any trace is found, you will be punished severely and devastatingly.
- Preserve license/copyright notices and concise upstream attribution.
- Sign non-obvious/note comments with the author's name: `# note (name): ...`.
- No backticks in Python comments or docstrings. Identifiers stay in plain text: `"""Valid frame counts after the encoder's stride-2 conv2."""` is correct; wrapping the name in double backticks is not.
- NO process markers: no ★, `# P1`, `# [FIX]`, `# TODO` without a ticket, `# === SECTION ===` banners.
- NO provenance leakage: never name other repos/upstream/"the closed source" in source.
- Docstrings: Google-style, 1-3 lines. Args/Returns only when non-obvious. One short module docstring per file.
- Do not add opening comment blocks or lengthy explanations after class definitions. Use the short module docstring and brief explanations where needed.
- A long-term workaround gets a one-line comment naming the constraint.
- `# noqa: <code>` allowed with a reason; bare `# noqa` is not.

## NAMING

- Classes PascalCase; functions/variables snake_case; constants UPPER_SNAKE. Preserve language-defined special methods such as `__init__`.
- A leading underscore is a Python naming convention for a non-public name; it does not prevent callers from accessing that name. Use it for implementation details that are not part of the supported public interface. Do not add it to a name that is part of the public interface.
- **Name the represented concept clearly.** Every parameter, local variable, function, method, class, and type alias should make its domain meaning clear without requiring the reader to inspect the function body or another file. For quantities, include the unit when it is not clear from the name or surrounding interface. Expand abbreviations when they hide the meaning, and keep the same value under the same name throughout its call chain.
- Prefer full words. Avoid clipped words, unclear concatenated initialisms, and generic role names when the represented concept is known.
  Wrong: `op`, `SessionOp`, `rid`, `seq`, `cmd`, `ctx`, `req`, `fn`, `cb`, `tmp`, `data`, `info`, `item`, `obj`, `handler`, `manager`, `cu_seqlens`, `token_len`, `token_lens`, `feat`, `dev`, `key`, `args`, `h`, `c`.
  Right: `operation`, `SessionOperation`, `request_id`, `sequence`, `session_operation`, `session_context`, `request`, `request_compute`, `session_hooks`, `cumulative_sequence_lengths`, `token_lengths`, `resolved_device`, `reference_key`, `angles`, `hidden_states`.
  `cu_seqlens` is the prefix sum of per-sequence lengths, so it is `cumulative_sequence_lengths`. `token_len` / `token_lens` are `token_lengths`. A cache key for a reference input is `reference_key`, not `key`.
- Single letters only for loop indices (`i`, `j`) or math symbols that are the quantity (`x`, `y`, `t`, and established symbols such as `mu`, `q`, `k`, `v`, `dt`). A letter that stands for a role (`h` for hidden states, `c` for conditioning) is not math. Do not append `T` to invent a type name.
- Do not rename a name that is the external contract. Keep a checkpoint or config key, a state-dict module attribute, and a callee's parameter when you only pass it. Rename your own local and your own parameter.

## TYPING & SIGNATURES

- Full type hints on every function, method, and attribute. Annotate parameters and return types, including `-> None` on `__init__`. One syntax only: `X | Y`, `list[int]`, `dict[str, int]`, `X | None`. Do not introduce `Optional` or `Union`.
- Either `requires-python >= 3.10` (native `X | Y`) or `from __future__ import annotations`. A string annotation may refer to a type defined later or imported only for type checking; it postpones evaluation where annotations would otherwise be evaluated immediately. Quoting a name does not import it or guarantee that runtime annotation introspection can resolve it.
- `TYPE_CHECKING` is false at runtime and is treated as true by static type checkers. Use it only for imports needed exclusively by annotations, and account for runtime tools that evaluate annotations. Runtime dependencies belong in ordinary module-level imports. To resolve a genuine circular dependency, prefer moving a shared type to the module that constructs it when that keeps ownership clear; do not create a module solely to hold one type or replace a named record with an anonymous tuple.
- Closed value sets → `Literal[...]` or `Enum`, not bare strings in comparisons.
- No mutable function defaults: `def f(x=[])`/`= {}` are bugs. Use a `None` sentinel.
- Every annotation should make the expected values, fields, and relationships clear. Use built-in types, user-defined classes, dataclasses, TypedDict, NamedTuple, Enum, `Literal`, or unions as appropriate. Parameterize containers (`dict[str, int]`, `list[TokenId]`, `tuple[torch.Tensor, torch.Tensor]`). This applies to structured values, model and decoder types, and resource handles.
- Prefer annotations that preserve useful checking. `Any`, bare containers, and `Callable[..., T]` can hide details; use them only when the interface is genuinely dynamic. `Callable[[TimedChunk], None]` is suitable for a simple callback. Use a `Protocol` when the callback has keyword-only parameters, overloads, additional members, or a signature that `Callable` cannot express. `TypeVar` and related generic features are appropriate when they express a real relationship between types; do not add them without such a relationship. `Optional[T]` and `Union[...]` are valid typing forms, but this style uses `T | None` and `X | Y` consistently.
- `cast` changes the type assumed by a static checker and performs no runtime validation. Use it only when the value's type is established by a boundary that the checker cannot represent, and do not use it instead of validating untrusted input.
- Example: use `Callable[[TimedChunk], None]` for a callback with one positional parameter and no additional interface. Use a `ChunkEmitter` protocol when the callback needs a richer signature. Give the enclosing function a concrete return type such as `StagePayload`.
- `object` is valid when a value may have any runtime type; unlike `Any`, it requires narrowing before type-specific operations. For untrusted input, annotate it as `object` or `Mapping[str, object]`, validate its shape at the boundary, and pass a narrowed value inward.
- A callback `Protocol` must name its parameters and return type. Do not erase an unknown callback signature with `*args` or `**kwargs`. Use generic parameters when they accurately preserve a relationship between values; do not use them to claim that unrelated values share a type.
- Do not accept a parameter only to immediately delete it to silence type or lint checks, such as starting a function with `del request_id`. Remove unnecessary parameters and update callers. If an established interface requires an unused parameter, preserve the contract and make that constraint explicit rather than pretending the parameter is used.

## DATA STRUCTURES

- Internal value objects (config, messages, state): `@dataclass`, prefer `kw_only=True`; mutable defaults via `field(default_factory=...)`.
- Keep each dataclass specific to the component or concept it represents. Use a descriptive name and explicit, typed fields so its purpose and valid state are clear.
- Avoid catch-all dataclasses that represent unrelated configurations through mode flags, arbitrary option dictionaries, or many fields that apply to only one case. Model distinct concerns with separate dataclasses and compose them when needed.
- Share a base dataclass only when its fields have the same meaning and validation rules across the components that use it.
- Cross-boundary schemas (API req/resp, untrusted input, needs validation): `pydantic.BaseModel`. Don't hand-roll validators pydantic gives free.
- Don't mix the two for one concept. Pick per role, not per mood.
- Use `mapping.pop(key)` when the removed value is needed or when a default for a missing key is appropriate. Use `del mapping[key]` when the operation only removes the entry. Both forms name the mapping and key; choose according to whether the value or a default is needed.

## FILE STRUCTURE

- File > ~400 lines → extract a module. But a 30-line file holding one `_helper` called once is also wrong — merge it. Related functions belong together; one concern per file does not mean one function per file.
- One entry-point mechanism per repo (hydra/argparse/fire/`[project.scripts]`). `if __name__ == "__main__"` only in entry-point modules, never library modules.
- Module-level side effects (env mutation, global state, `setup_root`, resolver registration) only in entry-point modules. Library imports must be side-effect-free.
- No dead code: unreachable branches, commented-out blocks, stale TODOs, "kept for later" stubs.
- Update generated files through the project's generation process. Never hand-edit generated artifacts.

## ERROR HANDLING & MATURITY

- Use `assert` for developer checks of internal invariants. Python removes assert statements when run with optimization (`-O`), so do not use them for input validation or conditions that must be enforced in production.
- Raise an exception that describes the failure. For example, use `ValueError` for an invalid value and `FileNotFoundError` for a missing file; choose a more specific built-in or domain exception when one fits. These examples are not an exhaustive mapping of user-input and environment errors.
- No bare `except:` or `except Exception: pass`. Catch the narrowest useful exception. Use a broad handler only at a boundary that must recover from or translate otherwise unexpected failures; preserve useful diagnostics, and chain the original exception when translating it.
- Maturity progression — this matters:
  - Prototyping: try/except around the call you don't yet trust is fine.
  - Mature: remove debugging-only guards and workarounds once the contract is established. Keep error handling at boundaries that can recover from or report failures. Let unexpected exceptions propagate to an appropriate boundary instead of fabricating a successful result.
  - Review: every try/except and defensive `if` must answer "what breaks if I delete this?" If the answer is "nothing, it was for debugging" — delete it.
- Do not wrap large blocks in `try/except` to guard against speculative, extremely unlikely failures. Handle errors that realistically occur on the main execution path; let unexpected exceptions propagate to a boundary that can report or translate them.
- Do not turn execution failures into fabricated successful outputs. When a function guarantees a return type, use its result directly instead of adding impossible `None` checks or redundant type coercion. Validate genuinely untrusted results at their boundary instead of weakening an established internal contract.
- Access fields on known types directly. Do not use `getattr` defaults or `hasattr` probes to hide missing required attributes, or catch attribute errors for operations guaranteed by the interface. Missing required attributes should fail visibly rather than trigger a search for alternate fields or fallback defaults.

## CONTROL FLOW

- Validate inputs and preconditions before the main logic. Organize conditions into mutually exclusive if/elif/else branches. Keep the main execution path in the final branch.
- This style prefers exhaustive `if`/`elif`/`else` chains so each branch is explicit. Python permits an `if` statement without `else`; requiring `else` is a style preference, not a syntax rule. When the other branch intentionally does nothing, this style writes `else: pass`.

  Wrong:

  ```python
  if session is not None:
      close_session(session)
  payload.data = {"closed": True}
  ```

  Right:

  ```python
  if session is not None:
      close_session(session)
  else:
      pass
  payload.data = {"closed": True}
  ```

## LOGGING

- Use the logging library the repository already uses; if it has none, use stdlib `logging`. Configure once; don't introduce a second logging library.
- One logger per module: `logging.getLogger(__name__)`.
- Keep messages terse. No manual `[Info]`, `[Warn]`, or `[step N]` prefixes; use the logger's level and context fields.
- `print` only for CLI output the end user reads (`--help`, visualization, `__main__` demo). Runtime info — even debug — goes through the logger.
- With stdlib `logging`, pass variable data as arguments: `logger.info("Loading %s config=%s split=%s", repo_id, config_name, split)`. The logger formats the message only when it emits the record. For another logging library, follow its documented lazy-formatting API. Avoid eagerly building messages when the configured level may filter the record.

## CONFIG & MAGIC VALUES

- No hardcoded URLs, absolute paths, or hostnames. Required deployment values must come from validated configuration, without embedded machine-specific defaults.
- Replace unexplained magic numbers with named constants at module scope.
- Empirical constants named + provenance comment: `DECODE_TOKENS_PER_SECOND = 6.7  # measured on H20`.
- A user-facing option (a config file entry, an environment variable, or a command-line argument) must be worth tuning by the user.
  - Add one only when:
    1. You know that option A is sometimes better and option B is sometimes better, but the program cannot reliably decide which one to use, so the user must decide. For example, which parallelism strategy to use.
    2. The option has no objective better or worse value and depends entirely on personal choice. For example, log verbosity.
  - Never add one when:
    1. You know exactly which value to set under which condition, or one specific value is always better. Decide the value automatically in code.
    2. The option is only for temporary probing or experiments and is not used in production. Delete the option.
    3. The option is only for long-term testing and is not used in production. Implement a mock in the test code.
- Use one config mechanism, following the repository's existing choice (Hydra / argparse+yaml / dataclass / env). If none exists, pick the lightest that fits. Do not stack config dataclasses, YAML loaders, validators, and CLI overrides when argparse + dict would do.
- Document each public configuration field with a docstring placed immediately after its declaration.
- In a standalone test script or install script, prefer command-line arguments. Use an environment variable only as a last resort for special cases, such as an option that must be handled before Hydra initializes. If you add an environment variable, update the environment variable section of the related documents.
- Do not ship a YAML file that is "documentation only" and never loaded.
- Define a constant used by only one module in that module; do not create a cross-file import solely for it.
- Parameters flow top-down. A default owned by the top-level config (a config dataclass, a Hydra config, or the CLI) is written once at that layer and passed down. Do not re-declare the same value as a lower-layer module constant or factory default. The factory takes the knobs as required parameters and forwards them; it does not invent a second copy of the policy.
  Wrong: `MAX_BATCH_SIZE = 8` in the executor module plus `max_batch_size: int = 8` in the config dataclass.
  Right: only the config dataclass holds the default; `create_executor(..., max_batch_size: int, ...)` takes it as a required parameter.

## IMPORTS

- Group: stdlib / third-party / local, blank-line separated, alphabetical within group.
- Manage import paths consistently at the project level. Don’t patch sys.path ad hoc in individual files.
- Prefer module-scope imports so dependencies are visible at the top of the file. Python permits imports inside functions. Use a local import only for a concrete need, such as deferring an optional dependency or resolving a cycle that cannot be removed cleanly.
- A circular import does not always fail. It fails when a module accesses a name that the other module has not defined yet. Prefer moving shared behavior or types to a module with clear ownership. Use `TYPE_CHECKING` for imports needed only by annotations, as described above. If a runtime cycle remains necessary, a local import at the point of use can be valid; cover that path with a test. Do not move a type into a dataclass or a new module unless that matches its ownership.
- Keep the optional-dependency guards the repository already has. A new guard is a module-scope `try`/`except ImportError`.
- For repository-internal imports, import from the defining module using the full package path, such as `from xxx.yy.zzz import kkk`, rather than through `__init__.py`. Keep package re-exports minimal and define an explicit `__all__`; no wildcard imports. For third-party libraries, prefer their documented public import paths (e.g. `from pydantic import BaseModel`).
- Do not import a class or factory from a sibling model package. Shared runtime code belongs in a non-model module. Wrong: model A's code imports a scheduler defined in model B's package. Right: both models import the shared scheduler from the non-model module and pass their own model-specific parts.

## TOOLING & REVIEW

- Line length, quote style, and import order come from the repository's formatter and linter configuration. When the formatter leaves quote style alone, use double quotes.
- Before completing a change, run the linters, formatters, and type checks that the repository configures.
- In a review, flag violations of these rules in changed code that the configured linters and formatters do not enforce. Do not comment on subjective style preferences or on issues those tools already cover.

## TESTS

- Every test case should protect behavior required by the task or public interface. It should fail when that behavior regresses, not merely restate a constant or implementation expression.
- Tests may cover new or existing behavior, regressions, derived properties (boundary math, invariants, ordering, round trips, graph output equal to eager), and lifecycle or bookkeeping requirements (registry completeness, a field's lifecycle, a branch that must not fire, a value copied from an outside spec). A regression test should describe the observable failure it guards against.
- Avoid tests that only repeat an implementation formula, assert a default with no consumer, test standard-library behavior, or exercise only their own fake. Performance and load tests are appropriate when they protect an explicit requirement with repeatable inputs and a controlled environment. Use events, barriers, or other explicit synchronization to establish race interleavings; `sleep(0)` yields control but does not guarantee which task runs next.
- Mock an external or slow boundary only when the assertion still checks a result, a state change, an output or an error. Counting calls to a real operation, wrapped rather than replaced, is fine when skipping that work is the contract.
- One strong case beats several weak ones. Fold repetitive cases into one parametrized case, and keep a row only if it guards a failure no other row guards. A case is redundant only when another case makes the same assertions on the same input; running the same lines is not enough. Before deleting a case, name the regression it would let through.
- Do not weaken a case merely to make it pass or run faster: do not drop required assertions or stub the code under test. When changing a tolerance, base it on the required behavior and representative measurements. Use fixed seeds for stochastic inputs when reproducibility matters.
- Fakes and fixtures that several test files share live in one shared fixtures module; a test file never imports another test file.
- Test the public contract (inputs → outputs), not internal layout. Do not snapshot helper tuples, page tables, prefix sums, or other encodings that can change without changing behavior. A representation refactor that preserves the caller's result should not break tests.
- Do not add a new test file for one case that belongs next to the existing suite. Put optional-backend cases with related tests, use the project's markers, and skip when the backend is absent. Confirm that the intended CI job selects the marker.
- Test actual failure contracts and supported fallback paths; do not add tests solely to preserve speculative recovery scaffolding.
