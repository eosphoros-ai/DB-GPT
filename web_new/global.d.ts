declare namespace JSX {
  interface IntrinsicElements {
    summary: React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement>;
    'custom-view': React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement>;
    references: React.DetailedHTMLProps<
      React.HTMLAttributes<HTMLElement> & {
        title: string;
        references: any;
      },
      HTMLElement
    >;
    'chart-view': React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement>;
  }
}
