import { redirect } from 'next/navigation'

export default function KeysPage() {
  redirect('/dashboard?view=keys')
}
