const { NxAppWebpackPlugin } = require('@nx/webpack/app-plugin');
const { join } = require('path');

const isProduction = process.env.NODE_ENV === 'production';

// Build options live here rather than in project.json because the @nx/webpack:webpack executor
// is deprecated in Nx 23 and removed in Nx 24; `webpack-cli build` is what Nx itself runs now.
module.exports = {
  output: {
    // dist/apps/<metadata.appInfo.domain>/<metadata.appInfo.appName> — the layout the Dockerfiles copy from.
    path: join(__dirname, '../../dist/apps/fb-governance/fb-governance-portal-experience-api'),
    clean: true,
    ...(!isProduction && { devtoolModuleFilenameTemplate: '[absolute-resource-path]' }),
  },
  plugins: [
    new NxAppWebpackPlugin({
      target: 'node',
      compiler: 'tsc',
      main: './src/main.ts',
      tsConfig: './tsconfig.app.json',
      assets: ['./src/assets'],
      optimization: false,
      outputHashing: 'none',
      // Workspace libs (tsconfig paths) are bundled into main.js; npm packages stay external and
      // are resolved from the monorepo-base image's node_modules.
      externalDependencies: 'all',
      // Lists the API's exact runtime dependencies next to main.js for image scanning / audit.
      generatePackageJson: isProduction,
      sourceMap: true,
    }),
  ],
};
