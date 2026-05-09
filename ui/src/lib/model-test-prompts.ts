export const MODEL_TEST_PROMPTS_SETTING_KEY = 'model_test_prompts'

export const DEFAULT_MODEL_TEST_PROMPTS = [
  '请直接回答：一个篮子里有 3 个苹果，又放入 2 个苹果，再拿走 1 个，还剩几个？',
  '请用两句话讲一个关于月亮和程序员的短故事。',
  '请判断这句话是否矛盾，并简短说明理由：所有模型都会失败，但这个模型没有失败。',
] as const

export function parseModelTestPrompts(value: string | null | undefined): string[] {
  const prompts = (value ?? '')
    .replace(/\r/g, '\n')
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
  return prompts.length ? prompts : [...DEFAULT_MODEL_TEST_PROMPTS]
}

export function serializeModelTestPrompts(value: string): string {
  return parseModelTestPrompts(value).join('\n')
}
