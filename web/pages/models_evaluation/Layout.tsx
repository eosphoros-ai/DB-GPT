import { EvaluationItemProvider } from "./context/EvaluationContext"

export const Layout = ({children}: { children: React.ReactNode}) => {
  return (
    <EvaluationItemProvider>
      {children}
    </EvaluationItemProvider>
  )
}