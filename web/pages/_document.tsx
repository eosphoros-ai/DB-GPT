import Document, { Head, Html, Main, NextScript } from 'next/document';

class MyDocument extends Document {
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
