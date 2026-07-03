import { Fragment } from 'react'

type LegalMotionTitleProps = {
  title: string
}

export const LegalMotionTitle = ({ title }: LegalMotionTitleProps) => {
  const words = title.split(' ')

  return (
    <h1 className='legal-page-title'>
      {words.map((word, index) => (
        <Fragment key={`${word}-${index}`}>
          {index > 0 ? ' ' : null}
          <span
            className='legal-title-word'
            style={{ animationDelay: `${0.18 + 0.09504 * index}s` }}
          >
            {word}
          </span>
        </Fragment>
      ))}
    </h1>
  )
}
