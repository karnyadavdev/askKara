import { useAppDispatch, useAppSelector } from '../app/hooks'
import { toggleThinking } from '../features/streamSlice'

export default function ThinkingToggle() {
  const dispatch = useAppDispatch()
  const deep = useAppSelector((state) => state.stream.deep)
  const thinking = useAppSelector((state) => state.stream.thinking)

  if (deep) return null

  const highest = thinking === 'high'

  return (
    <button
      type="button"
      className={`thinking-toggle${highest ? ' active' : ''}`}
      aria-pressed={highest}
      onClick={() => dispatch(toggleThinking())}
    >
      THINKING: {highest ? 'HIGHEST' : 'LOW'}
    </button>
  )
}
