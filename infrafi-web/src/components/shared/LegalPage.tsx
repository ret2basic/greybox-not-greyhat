import type { ReactNode } from 'react'

import { LegalMotionTitle } from './LegalMotionTitle'

type LegalPageProps = {
  title: string
  /** Sub-title line shown above the heading (e.g. effective date). */
  meta: ReactNode
  children: ReactNode
}

/**
 * Shared shell for the InfraFi legal pages (Terms / Privacy). Mirrors the
 * DAWN website's legal layout (`legal-page-*` + `rich-text-block` classes
 * in styles/legal.css) so usd.tel hosts these documents with the same
 * styling rather than linking out to dawninternet.com.
 */
export const LegalPage = ({ title, meta, children }: LegalPageProps) => {
  return (
    <main className='mx-auto w-full max-w-[1080px] px-4 sm:px-6 lg:px-8'>
      <div className='legal-page-container'>
        <div className='legal-page-content'>
          <header className='legal-page-header'>
            <div className='blog-title-info w-full'>
              <div className='legal-page-date'>{meta}</div>
              <LegalMotionTitle title={title} />
            </div>
          </header>

          <div className='rich-text-block'>{children}</div>
        </div>
      </div>
    </main>
  )
}
