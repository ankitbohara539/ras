import { useEffect, useState } from 'react'

type ProfileAvatarProps = {
  name: string | null | undefined
  email: string
  url?: string | null
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const sizes = {
  sm: 'size-9 text-xs',
  md: 'size-11 text-sm',
  lg: 'size-20 text-2xl',
}

export function ProfileAvatar({
  name,
  email,
  url,
  size = 'md',
  className = '',
}: ProfileAvatarProps) {
  const [failed, setFailed] = useState(false)
  const displayName = name?.trim() || email
  const initials = displayName
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase()

  useEffect(() => setFailed(false), [url])

  return (
    <span
      className={`relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full border border-line bg-brand-soft font-bold text-brand shadow-sm ${sizes[size]} ${className}`}
      aria-label={`${displayName} profile photo`}
    >
      {url && !failed ? (
        <img
          src={url}
          alt=""
          className="h-full w-full object-cover"
          onError={() => setFailed(true)}
        />
      ) : (
        <span aria-hidden="true">{initials || '?'}</span>
      )}
    </span>
  )
}
