import { createCache, StyleProvider } from '@ant-design/cssinjs';
import Document, { DocumentContext, Head, Html, Main, NextScript } from 'next/document';
import { doExtraStyle } from '../genAntdCss';

class MyDocument extends Document {
  static async getInitialProps(ctx: DocumentContext) {
    const cache = createCache();
    let fileName = '';
    const originalRenderPage = ctx.renderPage;
    ctx.renderPage = () =>
      originalRenderPage({
        enhanceApp: App => props => (
          <StyleProvider cache={cache} hashPriority='high'>
            <App {...props} />
          </StyleProvider>
        ),
      });
    const initialProps = await Document.getInitialProps(ctx);

    fileName = doExtraStyle({
      cache,
    });

    return {
      ...initialProps,
      styles: (
        <>
          {initialProps.styles}
          {/* 1.2 inject css */}
          {fileName && <link rel='stylesheet' href={`/${fileName}`} />}
        </>
      ),
    };
  }

  render() {
    return (
      <Html lang='zh'>
        <Head>
          <link rel='icon' href='/zhongke-zhonghuan-logo.png' />
          <meta name='description' content='中涣问数 - 智能数据库交互与数据分析平台' />
          <meta property='og:description' content='中涣问数 - 智能数据库交互与数据分析平台' />
          <meta property='og:title' content='中涣问数' />
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
