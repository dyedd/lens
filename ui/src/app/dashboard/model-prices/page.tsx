import { redirect } from 'next/navigation'

export default function DashboardModelPricesPage() {
  redirect('/dashboard?view=model-prices')
}
