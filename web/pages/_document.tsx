import { createCache, StyleProvider } from '@ant-design/cssinjs';
import Document, { DocumentContext, Head, Html, Main, NextScript } from 'next/document';
import { doExtraStyle } from '../genAntdCss';

interface Props {
  currentUrl: string;
}

class MyDocument extends Document<Props> {
  static async getInitialProps(ctx: DocumentContext) {
    const cache = createCache();
    let fileName = '';
    const originalRenderPage = ctx.renderPage;
    ctx.renderPage = () =>
      originalRenderPage({
        enhanceApp: (App) => (props) =>
          (
            <StyleProvider cache={cache}>
              <App {...props} />
            </StyleProvider>
          ),
      });
    const initialProps = await Document.getInitialProps(ctx);
    const currentUrl = ctx.req?.url;

    fileName = doExtraStyle({
      cache,
    });

    return {
      ...initialProps,
      currentUrl,
      styles: (
        <>
          {initialProps.styles}
          {/* 1.2 inject css */}
          {fileName && <link rel="stylesheet" href={`/${fileName}`} />}
        </>
      ),
    };
  }

  render() {
    return (
      <Html lang="en">
        <Head>
          <link rel="icon" href="/favicon.ico" />
          <meta name="description" content="Revolutionizing Database Interactions with Private LLM Technology" />
          <meta property="og:site_name" content="dbgpt.site" />
          <meta property="og:description" content="eosphoros-ai" />
          <meta property="og:title" content="DB-GPT" />
        </Head>
        <body>
          <Main />
          <NextScript />
        </body>
      </Html>
    );
  }
}

export default MyDocument;
