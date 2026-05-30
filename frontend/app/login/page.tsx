import LoginForm from "@/components/LoginForm"

export default function LoginPage() {
  return (
    <main className="mx-auto max-w-md px-4 py-16">
      <h1 className="mb-8 text-2xl font-bold text-gray-900">
        Sign in to Corvus
      </h1>
      <LoginForm />
    </main>
  )
}
