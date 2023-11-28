import React from 'react';
import Flickity from 'react-flickity-component';
import Link from '@docusaurus/Link';
import FeaturedSlides from './slides.json';
import './flickity.css';
import clsx from 'clsx';
import styles from './styles.module.css';

const flickityOptions = {
  initialIndex: 0,
  autoPlay: false,
  adaptiveHeight: true,
  wrapAround: true,
  groupCells: false,
  fade: true,
  pageDots: false,
};

export default function FeaturedSlider() {
  const RenderSlides: () => void = () => {
    return FeaturedSlides.map((slide) => (
      <div key={slide.title} className={clsx(styles.slide__container)}>
        <div
          key={slide.title}
          className={clsx(styles.slide)}
          style={{
            backgroundColor: 'transparent',
            backgroundImage: ` url(${slide.imagePath})`,
            backgroundSize: '35%',
            backgroundRepeat: 'no-repeat',
            backgroundPosition: 'bottom right',
          }}
        >
          <div className={clsx(styles.slide__section)}>
            <h1 className={clsx(styles.slide__header)}>{slide.title}</h1>
            <p className={clsx(styles.slide__description)}>
              {slide.description}
            </p>
            <div className={clsx(styles.slide__buttons)}>
              {slide.outlinedButton && (
                <Link
                  to={slide.outlinedButton.url}
                  className={clsx(
                    styles.slide__button,
                    'button',
                    'button--outline',
                    'button--primary',
                  )}
                >
                  {slide.outlinedButton.buttonText}
                </Link>
              )}
              {slide.solidButton && (
                <Link
                  to={slide.solidButton.url}
                  className={clsx(
                    styles.slide__button,
                    'button',
                    'button--primary',
                  )}
                >
                  {slide.solidButton.buttonText}
                </Link>
              )}
            </div>
          </div>
        </div>
      </div>
    ));
  };

  return (
    <Flickity
      options={flickityOptions}
    >
      <RenderSlides />
    </Flickity>
  );
}
