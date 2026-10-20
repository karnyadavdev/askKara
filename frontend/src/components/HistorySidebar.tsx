type Props = {
  open: boolean
  items: { id: string; title: string }[]
  onClose: () => void
  onOpen: (id: string) => void
  onNew: () => void
}

export default function HistorySidebar({ open, items, onClose, onOpen, onNew }: Props) {
  return (
    <aside className={`sidebar-panel${open ? ' open' : ''}`}>
      <div className="sidebar-header">
        <h3>Chats</h3>
        <button className="close-btn" onClick={onClose}>
          &times;
        </button>
      </div>
      <div className="sidebar-new">
        <button className="menu-btn" onClick={onNew}>
          NEW CHAT
        </button>
      </div>
      <div className="sidebar-content">
        {items.length === 0 ? (
          <div className="sidebar-item sidebar-empty">Nothing yet.</div>
        ) : (
          items.map((item) => (
            <div key={item.id} className="sidebar-item" onClick={() => onOpen(item.id)}>
              {item.title}
            </div>
          ))
        )}
      </div>
    </aside>
  )
}
