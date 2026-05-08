import Image from 'next/image'

type AvatarProps = {
  size?: number
}

type AvatarComponent = (props: AvatarProps) => React.JSX.Element

type BrandIconDefinition = {
  prefixes: string[]
  src: string
  imageClassName?: string
  invertInDark?: boolean
}

function joinClassNames(...values: Array<string | undefined>) {
  return values.filter(Boolean).join(' ')
}

const BRAND_ICONS: BrandIconDefinition[] = [
  { prefixes: ['gpt-', 'o1', 'o3', 'o4', 'chatgpt', 'openai'], src: '/brand-icons/gpt.svg', imageClassName: 'scale-[0.94]', invertInDark: true },
  { prefixes: ['claude', 'anthropic'], src: '/brand-icons/claude.svg', imageClassName: 'scale-[0.96]', invertInDark: true },
  { prefixes: ['gemini', 'gemma', 'google'], src: '/brand-icons/gemini.svg', imageClassName: 'scale-[0.94]' },
  { prefixes: ['deepseek'], src: '/brand-icons/deepseek.svg', imageClassName: 'scale-[0.94]' },
  { prefixes: ['qwen', 'qwq', 'alibaba'], src: '/brand-icons/qwen.svg', imageClassName: 'scale-[0.94]' },
  { prefixes: ['moonshot', 'kimi'], src: '/brand-icons/kimi.svg', imageClassName: 'scale-[0.94]', invertInDark: true },
  { prefixes: ['glm', 'chatglm', 'zhipu', 'z-ai'], src: '/brand-icons/glm.svg', imageClassName: 'scale-[0.94]', invertInDark: true },
  { prefixes: ['minimax', 'abab', 'minmax'], src: '/brand-icons/minmax.svg', imageClassName: 'scale-[0.92]' },
]

const fallbackIcon: BrandIconDefinition = {
  prefixes: [],
  src: '/logo.svg',
  imageClassName: 'scale-[0.72]',
}

function createAvatar(definition: BrandIconDefinition): AvatarComponent {
  return function BrandAvatar({ size = 40 }: AvatarProps) {
    return (
      <span className="inline-flex shrink-0 items-center justify-center" style={{ width: size, height: size }}>
        <Image
          src={definition.src}
          alt=""
          width={size}
          height={size}
          className={joinClassNames(
            'h-full w-full object-contain',
            definition.imageClassName,
            definition.invertInDark ? 'dark:invert' : undefined
          )}
        />
      </span>
    )
  }
}

const iconEntries = BRAND_ICONS.map((item) => ({
  prefixes: item.prefixes,
  Avatar: createAvatar(item),
}))

const fallbackAvatar = createAvatar(fallbackIcon)

export function getModelGroupAvatar(name: string): AvatarComponent {
  const normalized = (name.includes('/') ? name.split('/')[1] : name).trim().toLowerCase()
  for (const item of iconEntries) {
    if (item.prefixes.some((prefix) => normalized.startsWith(prefix))) {
      return item.Avatar
    }
  }
  return fallbackAvatar
}

export function ModelAvatar({ name, size }: { name: string; size?: number }) {
  const avatarFn = getModelGroupAvatar(name)
  return avatarFn({ size })
}
