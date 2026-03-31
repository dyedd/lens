import { redirect } from 'next/navigation'

export default function ChannelsPage() {
  redirect('/dashboard?view=channels')
}
