import { useAppDispatch, useAppSelector } from '../app/hooks'
import { toggleDeep } from '../features/streamSlice'

export default function DeepToggle() {
  const dispatch = useAppDispatch()
  const deep = useAppSelector((state) => state.stream.deep)

  return (
    <button
      type="button"
      className={`deep-toggle${deep ? ' active' : ''}`}
      aria-pressed={deep}
      onClick={() => dispatch(toggleDeep())}
    >
      DEEP RESEARCH
    </button>
  )
}
