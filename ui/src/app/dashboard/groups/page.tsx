import { redirect } from 'next/navigation'

export default function GroupsPage() {
  redirect('/dashboard?view=groups')
}
