import { LeftOutlined, RightOutlined } from '@ant-design/icons';
import { Children, useEffect, useId, useRef, useState, type ReactNode } from 'react';
import styles from './DashboardGallery.module.css';

export default function DashboardTemplateCarousel({
  children,
  label = '精选模板',
}: {
  children: ReactNode;
  label?: string;
}) {
  const trackRef = useRef<HTMLDivElement>(null);
  const trackId = useId();
  const count = Children.count(children);
  const [edges, setEdges] = useState({ previous: false, next: false });
  const drag = useRef<{ pointerId: number; x: number; scrollLeft: number; moved: boolean } | null>(null);
  const suppressClick = useRef(false);

  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;
    const update = () => {
      const previous = track.scrollLeft > 2;
      const next = track.scrollLeft < track.scrollWidth - track.clientWidth - 2;
      setEdges(current => (current.previous === previous && current.next === next ? current : { previous, next }));
    };
    const frame = requestAnimationFrame(update);
    const observer = new ResizeObserver(update);
    observer.observe(track);
    track.addEventListener('scroll', update, { passive: true });
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      track.removeEventListener('scroll', update);
    };
  }, [count]);

  const scrollTo = (left: number) => {
    trackRef.current?.scrollTo({
      left,
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
    });
  };
  const step = (direction: number) => {
    const track = trackRef.current;
    if (!track) return;
    const card = track.firstElementChild as HTMLElement | null;
    const distance = (card?.offsetWidth || track.clientWidth) + (parseFloat(getComputedStyle(track).columnGap) || 0);
    scrollTo(track.scrollLeft + direction * distance);
  };
  const finishDrag = () => {
    const track = trackRef.current;
    const gesture = drag.current;
    if (!track || !gesture) return;
    drag.current = null;
    delete track.dataset.dragging;
    if (track.hasPointerCapture(gesture.pointerId)) track.releasePointerCapture(gesture.pointerId);
    // A drag must not also open the template underneath the pointer.
    suppressClick.current = gesture.moved;
  };

  return (
    <div className={styles.carousel} data-testid='featured-template-carousel' aria-roledescription='轮播'>
      <button
        type='button'
        className={`${styles.carouselArrow} ${styles.carouselPrevious}`}
        aria-label={`向左浏览${label}`}
        aria-controls={trackId}
        disabled={!edges.previous}
        onClick={() => step(-1)}
      >
        <LeftOutlined />
      </button>
      <div
        ref={trackRef}
        id={trackId}
        className={styles.carouselTrack}
        role='group'
        aria-label={`${label}列表，可左右滑动`}
        tabIndex={0}
        onKeyDown={event => {
          if (event.target !== event.currentTarget) return;
          if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
            event.preventDefault();
            step(event.key === 'ArrowLeft' ? -1 : 1);
          } else if (event.key === 'Home' || event.key === 'End') {
            event.preventDefault();
            scrollTo(event.key === 'Home' ? 0 : event.currentTarget.scrollWidth);
          }
        }}
        onPointerDown={event => {
          suppressClick.current = false;
          if (event.pointerType !== 'mouse' || event.button !== 0) return;
          drag.current = {
            pointerId: event.pointerId,
            x: event.clientX,
            scrollLeft: event.currentTarget.scrollLeft,
            moved: false,
          };
        }}
        onPointerMove={event => {
          const gesture = drag.current;
          if (!gesture || gesture.pointerId !== event.pointerId) return;
          const delta = event.clientX - gesture.x;
          if (!gesture.moved && Math.abs(delta) < 6) return;
          gesture.moved = true;
          event.currentTarget.dataset.dragging = 'true';
          event.currentTarget.setPointerCapture(event.pointerId);
          event.currentTarget.scrollLeft = gesture.scrollLeft - delta;
          event.preventDefault();
        }}
        onPointerUp={finishDrag}
        onPointerCancel={finishDrag}
        onLostPointerCapture={finishDrag}
        onPointerLeave={() => {
          if (!drag.current?.moved) drag.current = null;
        }}
        onDragStart={event => event.preventDefault()}
        onClickCapture={event => {
          if (!suppressClick.current) return;
          suppressClick.current = false;
          event.preventDefault();
          event.stopPropagation();
        }}
      >
        {children}
      </div>
      <button
        type='button'
        className={`${styles.carouselArrow} ${styles.carouselNext}`}
        aria-label={`向右浏览${label}`}
        aria-controls={trackId}
        disabled={!edges.next}
        onClick={() => step(1)}
      >
        <RightOutlined />
      </button>
    </div>
  );
}
